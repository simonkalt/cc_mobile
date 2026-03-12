docker run -d \
  -p 8675:8675 \
  --env-file .env \
  --name cc_mobile_backend \
  cc-mobile-backend