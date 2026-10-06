#!/bin/sh
# Swaps GitLab's job ID token for a short-lived Google access token
# for the gitlab-deployer service account, and prints it.
# Needs: GCP_ID_TOKEN, WIF_PROVIDER, DEPLOYER_SA (set in .gitlab-ci.yml), plus curl and jq.
set -eu

FEDERATED_TOKEN=$(curl -sSf -X POST "https://sts.googleapis.com/v1/token" \
  -H "Content-Type: application/json" \
  -d "{
    \"audience\": \"//iam.googleapis.com/${WIF_PROVIDER}\",
    \"grantType\": \"urn:ietf:params:oauth:grant-type:token-exchange\",
    \"requestedTokenType\": \"urn:ietf:params:oauth:token-type:access_token\",
    \"scope\": \"https://www.googleapis.com/auth/cloud-platform\",
    \"subjectTokenType\": \"urn:ietf:params:oauth:token-type:jwt\",
    \"subjectToken\": \"${GCP_ID_TOKEN}\"
  }" | jq -r .access_token)

curl -sSf -X POST \
  "https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/${DEPLOYER_SA}:generateAccessToken" \
  -H "Authorization: Bearer ${FEDERATED_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"scope": ["https://www.googleapis.com/auth/cloud-platform"]}' \
  | jq -r .accessToken