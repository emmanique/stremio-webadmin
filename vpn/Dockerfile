FROM qmcgaw/gluetun:v3.41.3
RUN apk add --no-cache socat
COPY entrypoint.sh /stremio-vpn-entrypoint
RUN chmod 0755 /stremio-vpn-entrypoint
ENV STREMIO_VPN_CONFIG_DIR=/vpn
ENTRYPOINT ["/stremio-vpn-entrypoint"]
