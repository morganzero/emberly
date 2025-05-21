```
version: "3.9"

networks:
  sushiweb:
    external: true
services:
  emberly:
    image: docker.io/sushibox/emberly:latest
    container_name: emberly
    hostname: emberly.${DOMAIN}
    restart: always
    privileged: true
    cap_add:
      - NET_ADMIN
    security_opt:
      - no-new-privileges:true
    networks:
      - sushiweb
    environment:
      PUID: ${PUID}
      PGID: ${PGID}
      UMASK: ${UMASK}
    volumes:
      - /etc/timezone:/etc/timezone:ro
      - /etc/localtime:/etc/localtime:ro
      - /sbx/appdata/emberly:/app
      - /sbx/appdata/emberly/configs:/app/configs
      - /sbx/mnt/union-zfs/content:/content:ro
      - /sbx/mnt/union-zfs/emberly:/media
    labels:
      - "com.centurylinklabs.watchtower.enable=true"
    healthcheck:
      test: ["CMD", "pgrep", "-f", "python3 /app/emberly.py"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

```
docker run -d \
    --name emberly \
    --hostname emberly.${DOMAIN} \
    --restart always \
    --cap-add NET_ADMIN \
    --privileged \
    --security-opt no-new-privileges:true \
    --network sushiweb \
    -e PUID=${PUID} \
    -e PGID=${PGID} \
    -e UMASK=${UMASK} \
    -v /etc/timezone:/etc/timezone:ro \
    -v /etc/localtime:/etc/localtime:ro \
    -v /sbx/appdata/emberly:/app \
    -v /sbx/appdata/emberly/configs:/app/configs \
    -v /sbx/mnt/union-zfs/content:/content:ro \
    -v /sbx/mnt/union-zfs/emberly:/media \
    --label "com.centurylinklabs.watchtower.enable=true" \
    docker.io/sushibox/emberly:latest
```