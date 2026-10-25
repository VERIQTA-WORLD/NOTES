// Run scripts/configure_web.py to create config.js from real stack outputs.
window.AGENT_CONFIG = {
  ApiBase: "https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com",
  ClientId: "YOUR_PUBLIC_COGNITO_APP_CLIENT_ID",
  LoginDomain: "https://YOUR_PREFIX.auth.us-east-1.amazoncognito.com",
  CallbackUrl: "http://localhost:8080/"
};
