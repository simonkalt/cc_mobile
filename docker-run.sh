docker rm -f cc_mobile_backend 2>/dev/null || true
docker run -it \
  -p 8675:8675 \
  --env-file .env \
  --name cc_mobile_backend \
  cc-mobile-backend