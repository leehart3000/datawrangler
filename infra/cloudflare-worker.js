// Forwards every request for datawrangler.org to the Cloud Run service.
const ORIGIN = "https://datawrangler-722150411150.europe-west2.run.app";

export default {
  async fetch(request) {
    const incoming = new URL(request.url);

    // Send www.datawrangler.org visitors to datawrangler.org.
    if (incoming.hostname === "www.datawrangler.org") {
      incoming.hostname = "datawrangler.org";
      return Response.redirect(incoming.toString(), 301);
    }

    const target = new URL(incoming.pathname + incoming.search, ORIGIN);

    const headers = new Headers(request.headers);
    headers.delete("Host");
    headers.set("X-Forwarded-Host", incoming.host);
    headers.set("X-Forwarded-Proto", "https");

    return fetch(target, {
      method: request.method,
      headers: headers,
      body: request.body,
      redirect: "manual",
    });
  },
};