#!/bin/bash

# Run the complete engine inside a function so failures can be returned
# to the caller without using exit and without terminating a root shell.
promotion_main() {

PASS=0
FAIL=0

ok()   { echo "[PASS] $*"; PASS=$((PASS + 1)); }
fail() { echo "[FAIL] $*"; FAIL=$((FAIL + 1)); }
info() { echo "[INFO] $*"; }

MODE="${1:-}"
TAG="${2:-}"

PRIVATE_REPO="/root/stremio-libtorrent-server-webadmin"
PUBLIC_REPO="/root/stremio-webadmin-public"

WORK="/root/stremio-public-promotion-check"
STAGE="/root/stremio-public-promotion-stage"

EXPECTED_PRIVATE_URL="https://github.com/emmanique/stremio-webadmin-dev.git"
EXPECTED_PUBLIC_URL="https://github.com/emmanique/stremio-webadmin.git"

echo "============================================================"
echo " STREMIO PRIVATE -> PUBLIC RELEASE PROMOTION"
echo "============================================================"
echo "Mode : $MODE"
echo "Tag  : $TAG"

echo
echo "===== 1. ARGUMENTS ====="

case "$MODE" in
    --dry-run)
        ok "Dry-run mode activo"
        ;;
    --promote)
        ok "Promotion mode solicitado"
        ;;
    *)
        fail "Modo valido: --dry-run ou --promote"
        ;;
esac

if printf '%s\n' "$TAG" |
   grep -Eq '^v[0-9]+\.[0-9]+\.[0-9]+$'; then
    ok "Release tag valida"
else
    fail "Release tag invalida: $TAG"
fi

VERSION="${TAG#v}"

echo
echo "===== 2. PRIVATE REPOSITORY ====="

if [ -d "$PRIVATE_REPO/.git" ]; then
    ok "Private repository encontrado"
else
    fail "Private repository nao encontrado"
fi

if [ "$FAIL" -eq 0 ]; then
    cd "$PRIVATE_REPO"

    ORIGIN_URL="$(git remote get-url origin 2>/dev/null)"
    PUBLIC_URL="$(git remote get-url public 2>/dev/null)"

    [ "$ORIGIN_URL" = "$EXPECTED_PRIVATE_URL" ] &&
        ok "origin = private development" ||
        fail "origin inesperado"

    [ "$PUBLIC_URL" = "$EXPECTED_PUBLIC_URL" ] &&
        ok "public = public distribution" ||
        fail "public inesperado"

    if git diff --quiet && git diff --cached --quiet; then
        ok "Private worktree clean"
    else
        fail "Private worktree possui alteracoes tracked"
    fi
fi

echo
echo "===== 3. REFRESH PRIVATE ====="

if [ "$FAIL" -eq 0 ]; then
    # Private and public repositories intentionally reuse release
    # tag names for different Git objects. Never fetch release tags
    # implicitly into this working repository.
    #
    # Update only private origin/main. The requested private release
    # tag is validated independently against origin with ls-remote.
    if git fetch origin --prune --no-tags \
        '+refs/heads/main:refs/remotes/origin/main'; then
        ok "Private main actualizado sem importar tags"
    else
        fail "Falha no fetch de private origin/main"
    fi

    if git fetch public --prune --no-tags \
        '+refs/heads/main:refs/remotes/public/main'; then
        ok "Public main actualizado sem importar public tags"
    else
        fail "Falha no fetch de public/main"
    fi
fi

echo
echo "===== 4. PRIVATE TAG CONTRACT ====="

if [ "$FAIL" -eq 0 ]; then

    LOCAL_TAG_OBJECT="$(
        git rev-parse -q --verify \
            "refs/tags/$TAG" 2>/dev/null
    )"

    REMOTE_TAG_OBJECT="$(
        git ls-remote origin \
            "refs/tags/$TAG" 2>/dev/null |
        awk 'NR==1 {print $1}'
    )"

    REMOTE_TAG_COMMIT="$(
        git ls-remote origin \
            "refs/tags/$TAG^{}" 2>/dev/null |
        awk 'NR==1 {print $1}'
    )"

    # Lightweight tags do not have a peeled ^{} reference.
    if [ -z "$REMOTE_TAG_COMMIT" ]; then
        REMOTE_TAG_COMMIT="$REMOTE_TAG_OBJECT"
    fi

    echo "local tag object =$LOCAL_TAG_OBJECT"
    echo "remote tag object=$REMOTE_TAG_OBJECT"
    echo "remote tag commit=$REMOTE_TAG_COMMIT"

    if [ -z "$REMOTE_TAG_OBJECT" ]; then
        fail "Private tag inexistente no origin: $TAG"

    elif [ -z "$LOCAL_TAG_OBJECT" ]; then
        fail "Private tag inexistente localmente: $TAG"

    elif [ "$LOCAL_TAG_OBJECT" != "$REMOTE_TAG_OBJECT" ]; then
        fail "Local private tag diverge de origin/$TAG"

    else
        ok "Local private tag object = origin private tag object"
    fi
fi

if [ "$FAIL" -eq 0 ]; then

    LOCAL_TAG_COMMIT="$(
        git rev-list -n 1 "$TAG" 2>/dev/null
    )"

    echo "local tag commit =$LOCAL_TAG_COMMIT"
    echo "remote tag commit=$REMOTE_TAG_COMMIT"

    if [ "$LOCAL_TAG_COMMIT" = "$REMOTE_TAG_COMMIT" ]; then
        ok "Local private tag commit = origin private tag commit"
    else
        fail "Private tag commit local/remoto diverge"
    fi
fi

if [ "$FAIL" -eq 0 ]; then

    if git merge-base --is-ancestor \
        "$LOCAL_TAG_COMMIT" origin/main; then

        ok "Private tag integrada em origin/main"
    else
        fail "Private tag nao integrada em origin/main"
    fi
fi

echo
echo "===== 5. VERSION CONTRACT ====="

if [ "$FAIL" -eq 0 ]; then

    PLATFORM="$(
        git show "$TAG:FORK_VERSION" 2>/dev/null |
        tr -d '\r\n'
    )"

    SERVER="$(
        git show "$TAG:SERVER_VERSION" 2>/dev/null |
        tr -d '\r\n'
    )"

    WEBADMIN="$(
        git show "$TAG:webadmin/WEBADMIN_VERSION" 2>/dev/null |
        tr -d '\r\n'
    )"

    echo "Platform=$PLATFORM"
    echo "Server=$SERVER"
    echo "WebAdmin=$WEBADMIN"

    [ "$PLATFORM" = "$VERSION" ] &&
        ok "FORK_VERSION=$VERSION" ||
        fail "FORK_VERSION mismatch"

    [ "$WEBADMIN" = "$VERSION" ] &&
        ok "WEBADMIN_VERSION=$VERSION" ||
        fail "WEBADMIN_VERSION mismatch"

    [ -n "$SERVER" ] &&
        ok "SERVER_VERSION=$SERVER" ||
        fail "SERVER_VERSION vazio"
fi

echo
echo "===== 6. BUILD SANITIZED SNAPSHOT ====="

# Always rebuild the promotion workspace from an empty directory.
# Never reuse content from a previous promotion attempt.
if [ -e "$WORK" ]; then
    rm -rf -- "$WORK"
fi

if mkdir -p "$WORK"; then
    ok "Promotion workspace recriado vazio"
else
    fail "Falha ao recriar promotion workspace"
fi

if [ "$FAIL" -eq 0 ]; then

    if git archive "$TAG" |
       tar -x -C "$WORK"; then
        ok "Private snapshot exportado"
    else
        fail "Falha no git archive"
    fi

    rm -f "$WORK/.env"

    rm -rf "$WORK/.github/workflows"
    rm -f "$WORK/.github/UPSTREAM_BASE"
    rm -f "$WORK/.github/upstream-protected-paths.txt"
    rm -f "$WORK/.github/dependabot.yml"

    # Private release/promotion tooling must never be included
    # in the public distribution repository.
    rm -rf "$WORK/tools/release"

    ok "Snapshot sanitizado"
fi

echo
echo "===== 7. SECURITY GATES ====="

if [ "$FAIL" -eq 0 ]; then

    find "$WORK" -type f \
        \( \
          -name '.env' -o \
          -name '*.pem' -o \
          -name '*.key' -o \
          -name '*.p12' -o \
          -name '*.pfx' -o \
          -name '*.ovpn' -o \
          -name 'wg0.conf' -o \
          -name 'wireguard.conf' -o \
          -name 'credentials.json' -o \
          -name 'secrets.json' \
        \) \
        -print \
        > /tmp/stremio-promotion-sensitive.txt

    if [ ! -s /tmp/stremio-promotion-sensitive.txt ]; then
        ok "Nenhum ficheiro sensivel proibido"
    else
        fail "Ficheiros sensiveis encontrados"
        cat /tmp/stremio-promotion-sensitive.txt
    fi

    if [ ! -d "$WORK/.github/workflows" ]; then
        ok "Internal workflows removidos"
    else
        fail "Internal workflows presentes"
    fi

    if [ ! -e "$WORK/tools/release" ]; then
        ok "Private release tooling ausente do snapshot publico"
    else
        fail "Private release tooling presente no snapshot publico"
    fi

    if [ -f "$WORK/.env.example" ]; then
        ok ".env.example preservado"
    else
        fail ".env.example ausente"
    fi
fi

echo
echo "===== 8. REQUIRED SOURCE ====="

if [ "$FAIL" -eq 0 ]; then

    REQUIRED="
FORK_VERSION
SERVER_VERSION
README.md
QUICKSTART.md
pyproject.toml
uv.lock
start.sh
compose.yaml
src
webadmin
vpn
tests
"

    REQUIRED_FAIL=0

    while IFS= read -r ITEM
    do
        [ -z "$ITEM" ] && continue

        if [ ! -e "$WORK/$ITEM" ]; then
            echo "[FAIL] Missing: $ITEM"
            REQUIRED_FAIL=$((REQUIRED_FAIL + 1))
        fi
    done <<EOF
$REQUIRED
EOF

    if [ "$REQUIRED_FAIL" -eq 0 ]; then
        ok "Required functional source completo"
    else
        fail "$REQUIRED_FAIL required items ausentes"
    fi
fi

echo
echo "===== 9. PUBLIC REPOSITORY ====="

if [ "$FAIL" -eq 0 ]; then

    if [ -d "$PUBLIC_REPO/.git" ]; then
        ok "Public repository encontrado"
    else
        fail "Public repository local inexistente"
    fi
fi

if [ "$FAIL" -eq 0 ]; then

    cd "$PUBLIC_REPO"

    PUBLIC_ORIGIN="$(git remote get-url origin 2>/dev/null)"

    [ "$PUBLIC_ORIGIN" = "$EXPECTED_PUBLIC_URL" ] &&
        ok "Public origin correcto" ||
        fail "Public origin incorrecto"

    if git fetch origin --prune --tags; then
        ok "Public origin actualizado"
    else
        fail "Public fetch falhou"
    fi
fi

echo
echo "===== 10. PUBLIC MAIN CONTRACT ====="

if [ "$FAIL" -eq 0 ]; then

    LOCAL_MAIN="$(git rev-parse main)"
    REMOTE_MAIN="$(git rev-parse origin/main)"

    echo "local main =$LOCAL_MAIN"
    echo "remote main=$REMOTE_MAIN"

    if [ "$LOCAL_MAIN" = "$REMOTE_MAIN" ]; then
        ok "Public main sincronizado"
    else
        fail "Public local main diverge de origin/main"
    fi

    if git diff --quiet &&
       git diff --cached --quiet; then
        ok "Public worktree clean"
    else
        fail "Public worktree possui alteracoes"
    fi
fi

echo
echo "===== 11. PUBLIC TAG CONTRACT ====="

PUBLIC_TAG_EXISTS="no"

if [ "$FAIL" -eq 0 ]; then

    REMOTE_PUBLIC_TAG="$(
        git ls-remote \
            origin \
            "refs/tags/$TAG" \
            "refs/tags/$TAG^{}" |
        awk 'NR==1 {print $1}'
    )"

    if [ -n "$REMOTE_PUBLIC_TAG" ]; then
        PUBLIC_TAG_EXISTS="yes"
        info "$TAG ja existe no public"
    else
        ok "$TAG ainda nao existe no public"
    fi
fi

echo
echo "===== 12. EXISTING RELEASE CHECK ====="

if [ "$FAIL" -eq 0 ] &&
   [ "$PUBLIC_TAG_EXISTS" = "yes" ]; then

    EXISTING="/root/stremio-existing-public-release"

    rm -rf "$EXISTING"
    mkdir -p "$EXISTING"

    if git archive "$TAG" |
       tar -x -C "$EXISTING"; then

        # Historical public releases may contain files that became
        # private-only in later versions. Apply the current public
        # distribution policy to both sides before comparison.
        rm -f "$EXISTING/.env"

        rm -rf "$EXISTING/.github/workflows"
        rm -f "$EXISTING/.github/UPSTREAM_BASE"
        rm -f "$EXISTING/.github/upstream-protected-paths.txt"
        rm -f "$EXISTING/.github/dependabot.yml"

        rm -rf "$EXISTING/tools/release"

        if diff -qr "$WORK" "$EXISTING" \
            > /tmp/stremio-existing-release.diff; then

            ok "Existing public $TAG = sanitized private snapshot"
        else
            fail "Existing public $TAG difere do snapshot privado"
            sed -n '1,200p' \
                /tmp/stremio-existing-release.diff
        fi
    else
        fail "Falha ao exportar public $TAG"
    fi
fi

echo
echo "===== 13. PROMOTION ELIGIBILITY ====="

PROMOTION_ALLOWED="no"

if [ "$FAIL" -eq 0 ]; then

    if [ "$MODE" = "--dry-run" ]; then

        ok "Dry-run validation concluida"

    elif [ "$MODE" = "--promote" ]; then

        if [ "$PUBLIC_TAG_EXISTS" = "yes" ]; then
            fail "Promotion recusada: public tag ja existe"
        else
            PROMOTION_ALLOWED="yes"
            ok "Release elegivel para promocao"
        fi
    fi
fi

echo
echo "===== 14. PREPARE PUBLIC COMMIT ====="

NEW_PUBLIC_COMMIT=""
NEW_PUBLIC_TAG=""

if [ "$FAIL" -eq 0 ] &&
   [ "$PROMOTION_ALLOWED" = "yes" ]; then

    cd "$PUBLIC_REPO"

    git checkout main >/dev/null 2>&1

    if git reset --hard origin/main >/dev/null 2>&1; then
        ok "Public main preparado sobre origin/main"
    else
        fail "Falha ao preparar public main"
    fi
fi

if [ "$FAIL" -eq 0 ] &&
   [ "$PROMOTION_ALLOWED" = "yes" ]; then

    find . \
        -mindepth 1 \
        -maxdepth 1 \
        ! -name '.git' \
        -exec rm -rf -- {} +

    if cp -a "$WORK"/. .; then
        ok "Sanitized snapshot aplicado ao public worktree"
    else
        fail "Falha ao aplicar snapshot"
    fi
fi

if [ "$FAIL" -eq 0 ] &&
   [ "$PROMOTION_ALLOWED" = "yes" ]; then

    git add -A

    if git diff --cached --quiet; then
        fail "Promotion nao possui alteracoes para publicar"
    else
        ok "Public release possui alteracoes"
    fi
fi

if [ "$FAIL" -eq 0 ] &&
   [ "$PROMOTION_ALLOWED" = "yes" ]; then

    if git commit \
        -m "Release $VERSION"; then
        ok "Public release commit criado"
    else
        fail "Falha ao criar public commit"
    fi
fi

if [ "$FAIL" -eq 0 ] &&
   [ "$PROMOTION_ALLOWED" = "yes" ]; then

    NEW_PUBLIC_COMMIT="$(git rev-parse HEAD)"
    PARENT="$(git rev-parse HEAD^)"

    echo "new public commit=$NEW_PUBLIC_COMMIT"
    echo "public parent=$PARENT"

    if [ "$PARENT" = "$REMOTE_MAIN" ]; then
        ok "Novo commit e filho directo do public main anterior"
    else
        fail "Parent do public commit inesperado"
    fi
fi

echo
echo "===== 15. VERIFY PUBLIC COMMIT CONTENT ====="

if [ "$FAIL" -eq 0 ] &&
   [ "$PROMOTION_ALLOWED" = "yes" ]; then

    VERIFY="/root/stremio-public-commit-verify"

    rm -rf "$VERIFY"
    mkdir -p "$VERIFY"

    if git archive HEAD |
       tar -x -C "$VERIFY"; then

        if diff -qr "$WORK" "$VERIFY" \
            > /tmp/stremio-public-commit.diff; then

            ok "Public commit = sanitized private snapshot"
        else
            fail "Public commit content mismatch"
            sed -n '1,200p' \
                /tmp/stremio-public-commit.diff
        fi
    else
        fail "Falha ao verificar public commit"
    fi
fi

echo
echo "===== 16. CREATE PUBLIC TAG ====="

if [ "$FAIL" -eq 0 ] &&
   [ "$PROMOTION_ALLOWED" = "yes" ]; then

    if git tag -a "$TAG" \
        -m "Stremio WebAdmin $VERSION"; then

        NEW_PUBLIC_TAG="$(
            git rev-list -n 1 "$TAG"
        )"

        if [ "$NEW_PUBLIC_TAG" = "$NEW_PUBLIC_COMMIT" ]; then
            ok "Public tag criada sobre novo release commit"
        else
            fail "Public tag target inesperado"
        fi
    else
        fail "Falha ao criar public tag"
    fi
fi

echo
echo "===== 17. FINAL PRE-PUSH GATE ====="

if [ "$FAIL" -eq 0 ] &&
   [ "$PROMOTION_ALLOWED" = "yes" ]; then

    if git diff --quiet &&
       git diff --cached --quiet; then
        ok "Public worktree clean antes do push"
    else
        fail "Public worktree nao esta clean"
    fi

    REMOTE_BEFORE="$(
        git ls-remote origin refs/heads/main |
        awk '{print $1}'
    )"

    if [ "$REMOTE_BEFORE" = "$REMOTE_MAIN" ]; then
        ok "Remote public main nao mudou durante promocao"
    else
        fail "Remote public main mudou durante promocao"
    fi

    REMOTE_TAG_BEFORE="$(
        git ls-remote origin \
            "refs/tags/$TAG" \
            "refs/tags/$TAG^{}"
    )"

    if [ -z "$REMOTE_TAG_BEFORE" ]; then
        ok "Public tag continua livre"
    else
        fail "Public tag apareceu durante promocao"
    fi
fi

echo
echo "===== 18. PUBLICATION ====="

if [ "$FAIL" -eq 0 ] &&
   [ "$PROMOTION_ALLOWED" = "yes" ]; then

    echo "Publishing:"
    echo "  main: $REMOTE_MAIN -> $NEW_PUBLIC_COMMIT"
    echo "  tag : $TAG -> $NEW_PUBLIC_COMMIT"

    if git push --atomic origin \
        "HEAD:refs/heads/main" \
        "refs/tags/$TAG:refs/tags/$TAG"; then

        ok "Atomic public main + tag push concluido"
    else
        fail "Atomic publication falhou"
    fi
else
    info "Nenhum push executado"
fi

echo
echo "===== 19. POST-PUBLISH VERIFY ====="

if [ "$FAIL" -eq 0 ] &&
   [ "$PROMOTION_ALLOWED" = "yes" ]; then

    REMOTE_AFTER="$(
        git ls-remote origin refs/heads/main |
        awk '{print $1}'
    )"

    REMOTE_TAG_AFTER="$(
        git ls-remote origin \
            "refs/tags/$TAG^{}" |
        awk '{print $1}'
    )"

    echo "remote main=$REMOTE_AFTER"
    echo "remote tag =$REMOTE_TAG_AFTER"

    [ "$REMOTE_AFTER" = "$NEW_PUBLIC_COMMIT" ] &&
        ok "Remote public main confirmado" ||
        fail "Remote public main inesperado"

    [ "$REMOTE_TAG_AFTER" = "$NEW_PUBLIC_COMMIT" ] &&
        ok "Remote public tag confirmado" ||
        fail "Remote public tag inesperado"
fi

echo
echo "===== 20. PRIVATE INTEGRITY ====="

cd "$PRIVATE_REPO"

PRIVATE_BRANCH="$(git branch --show-current)"
PRIVATE_HEAD="$(git rev-parse HEAD)"

echo "Private branch=$PRIVATE_BRANCH"
echo "Private HEAD=$PRIVATE_HEAD"

if [ "$PRIVATE_BRANCH" = "main" ]; then
    ok "Private repository permaneceu em main"
else
    fail "Private branch mudou inesperadamente"
fi

if [ "$MODE" = "--dry-run" ]; then
    ok "Dry-run nao publicou codigo"
fi

echo
echo "============================================================"
echo " RESULT"
echo "============================================================"
echo "PASS=$PASS"
echo "FAIL=$FAIL"

if [ "$MODE" = "--promote" ] &&
   [ "$PROMOTION_ALLOWED" = "yes" ]; then
    echo "Public release: $TAG"
    echo "Public commit : $NEW_PUBLIC_COMMIT"
fi

rm -f \
    /tmp/stremio-promotion-sensitive.txt \
    /tmp/stremio-existing-release.diff \
    /tmp/stremio-public-commit.diff

cd /root

if [ "$FAIL" -eq 0 ]; then
    return 0
else
    return 1
fi
}

promotion_main "$@"
