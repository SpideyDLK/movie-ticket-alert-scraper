import { launch } from "@cloudflare/playwright";

const SCOPE_URL = "https://www.scopecinemas.com/movies/coming-soon";

const SCOPE_API_PATH = "/movies/coming-soon";

export default {
  async fetch(request, env) {
    if (request.method !== "POST") {
      return Response.json({ error: "Method not allowed" }, { status: 405 });
    }

    const authorization = request.headers.get("Authorization");

    if (
      !env.HELPER_API_KEY ||
      authorization !== `Bearer ${env.HELPER_API_KEY}`
    ) {
      return Response.json({ error: "Unauthorized" }, { status: 401 });
    }

    let browser;

    try {
      browser = await launch(env.MYBROWSER);

      const page = await browser.newPage();

      // Register the listener before navigating so we don't
      // miss the request that contains the Next-Action header.
      const requestPromise = page.waitForRequest(
        (req) => req.method() === "POST" && req.url().includes(SCOPE_API_PATH),
        { timeout: 60000 },
      );

      await page.goto(SCOPE_URL, {
        waitUntil: "domcontentloaded",
        timeout: 60000,
      });

      const scopeRequest = await requestPromise;
      const headers = scopeRequest.headers();
      const nextActionId = headers["next-action"];

      if (!nextActionId) {
        throw new Error("Scope request did not contain a Next-Action header");
      }

      return Response.json({ nextActionId });
    } catch (error) {
      console.error("Failed to refresh Scope Next-Action ID", error);

      return Response.json(
        { error: "Failed to refresh Next-Action ID" },
        { status: 502 },
      );
    } finally {
      if (browser) {
        await browser.close();
      }
    }
  },
};
