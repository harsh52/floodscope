// Resolve a public asset path against the app base (works in dev and built).
export const asset = (p: string): string =>
  import.meta.env.BASE_URL.replace(/\/$/, "") + "/" + p.replace(/^\//, "");
