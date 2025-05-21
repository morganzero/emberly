```
version: "3.9"

networks:
  sushiweb:
    external: true

services:
  emberly:
    hostname: emberly.${DOMAIN}
    container_name: emberly
    image: docker.io/sushibox/emberly:latest
    restart: always
    healthcheck:
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    networks:
      - sushiweb
    cap_add:
      - NET_ADMIN
    privileged: true
    security_opt:
      - no-new-privileges:true
    environment:
      - PUID=${PUID}
      - PGID=${PGID}
      - UMASK=${UMASK}
    volumes:
      - "/etc/timezone:/etc/timezone:ro"
      - "/etc/localtime:/etc/localtime:ro"
      - "/sbx/appdata/emberly:/"
      - "/sbx/appdata/emberly/configs/config.yaml:/configs/config.yaml"
      - "/sbx/mnt/union-zfs/content:/media:ro"
      - "/sbx/mnt/union-zfs/emberly:/emberly"
    labels:
      - "com.centurylinklabs.watchtower.enable=true"
```

```
docker run -d   
    --name emberly   
    --hostname emberly.${DOMAIN}   
    --restart always   
    --cap-add NET_ADMIN   
    --privileged   
    --security-opt no-new-privileges:true   
    --network sushiweb   
    -e PUID=${PUID}   
    -e PGID=${PGID}   
    -e UMASK=${UMASK}   
    -v /etc/timezone:/etc/timezone:ro   
    -v /etc/localtime:/etc/localtime:ro   
    -v /sbx/appdata/emberly/config.yaml:/app/config.yaml   
    -v /sbx/mnt/union-zfs/content:/content-vault/content:ro   
    -v /sbx/mnt/union-zfs/emberly:/emberly   
    --label "com.centurylinklabs.watchtower.enable=true"   
docker.io/sushibox/emberly:latest
```