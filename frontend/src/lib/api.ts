const API_URL = (import.meta.env.PUBLIC_API_URL || '').replace(/\/$/, '');

if (!API_URL) {
    console.warn('[api] PUBLIC_API_URL is not set — API calls will fail. Set it in your Vercel environment variables.');
}

export async function list(resource: string): Promise<any[]> {
    if (!API_URL) return [];

    const cleanResource = resource.replace(/\/$/, '');
    const separator = cleanResource.includes('?') ? '&' : '?';
    const url = `${API_URL}/${cleanResource}${separator}format=json`;

    try {
        const response = await fetch(url);
        if (!response.ok) {
            console.error(`[api] list(${resource}) failed: HTTP ${response.status}`);
            return [];
        }
        const data = await response.json();
        // DRF returns { results: [...] } for paginated endpoints
        return Array.isArray(data) ? data : (data.results ?? []);
    } catch (err) {
        console.error(`[api] list(${resource}) error:`, err);
        return [];
    }
}

export async function get(resource: string, id: string): Promise<any | null> {
    if (!API_URL) return null;

    const url = `${API_URL}/${resource}/${id}/?format=json`;

    try {
        const response = await fetch(url);
        if (!response.ok) {
            console.error(`[api] get(${resource}, ${id}) failed: HTTP ${response.status}`);
            return null;
        }
        return await response.json();
    } catch (err) {
        console.error(`[api] get(${resource}, ${id}) error:`, err);
        return null;
    }
}
