import type { Handle } from "@sveltejs/kit";

/** Sin caché ni en el navegador ni en proxies: el dashboard cambia en T-24h/6h/1h. */
export const handle: Handle = async ({ event, resolve }) => {
  const response = await resolve(event);
  response.headers.set("cache-control", "no-store, must-revalidate");
  return response;
};
