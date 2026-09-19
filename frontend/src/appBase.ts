export function appBase(): string {
  if (typeof window === "undefined") return "";
  const w = window.__ATKBRAIN_BASE__;
  if (typeof w === "string" && w.startsWith("/")) return w.replace(/\/$/, "");
  return "";
}

export function withAppBase(path: string): string {
  const b = appBase();
  if (!path.startsWith("/")) return path;
  return b ? `${b}${path}` : path;
}
