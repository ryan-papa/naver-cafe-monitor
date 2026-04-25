# Docker Blue/Green Deployment

This repo owns the application containers for Naver Cafe Monitor.

## Secrets

Runtime secrets stay in `.env.enc`. The deploy script decrypts it in memory and passes values to `docker compose`; it does not write a plaintext `.env` file.

Required encrypted keys for the API container:

- `MYSQL_PASSWORD`
- `AUTH_AES_KEY`
- `AUTH_HMAC_KEY`
- `AUTH_JWT_SECRET`
- `AUTH_RSA_PRIVATE_KEY`
- `AUTH_RSA_PUBLIC_KEY`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_ADMIN_ALLOWED_EMAILS`
- `GOOGLE_OAUTH_REDIRECT_URI`
- `GOOGLE_OAUTH_SUCCESS_URL`
- `KAKAO_CLIENT_ID`
- `KAKAO_CLIENT_SECRET`

Optional deployment overrides can be set as runner environment variables:

- `MYSQL_HOST`, default `eepp.shop`
- `MYSQL_PORT`, default `3306`
- `MYSQL_USER`, default `rp_readwrite`
- `MYSQL_DATABASE`, default `naver_cafe_monitor`
- `MYSQL_SSL_CERT_DIR_HOST`, default `$HOME/.ssl/client-certs`

## Deploy Flow

By default, `scripts/deploy/docker_bluegreen_deploy.sh` keeps compatibility with the existing host nginx by deploying the green containers on the fixed upstream ports `4321` and `8000`.

Set `INFRA_SWITCH_ENABLED=1` only after `deploy-infra` nginx owns ports `80` and `443`.

With `INFRA_SWITCH_ENABLED=1`, the script:

1. Pulls the target branch.
2. Reads the active color from the infra repo.
3. Builds and starts the inactive color.
4. Checks API `/api/health` and web `/`.
5. Calls `deploy-infra/scripts/switch-upstream.sh`.
6. Stops the old color.
