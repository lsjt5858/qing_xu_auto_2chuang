// Self-contained: Chrome serializes this function into MAIN world, without imports or credentials.
export async function readIdentityInMain(): Promise<{
  uid: string; nickname: string; unique_id: string; short_id: string;
} | null> {
  try {
    const response = await fetch('/web/api/media/user/info/', {
      credentials: 'include', cache: 'no-store', redirect: 'error', signal: AbortSignal.timeout(5000),
    });
    if (!response.ok) return null;
    const result = await response.json();
    if (result?.status_code !== 0 || !result.user || typeof result.user !== 'object') return null;
    const { uid, nickname, unique_id, short_id } = result.user;
    if (typeof uid !== 'string' || !uid.trim() || typeof nickname !== 'string'
      || typeof unique_id !== 'string' || typeof short_id !== 'string') return null;
    return { uid, nickname, unique_id, short_id };
  } catch {
    return null;
  }
}
