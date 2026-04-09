const API_URL = (import.meta.env.PUBLIC_API_URL || 'http://localhost:9999/api').replace(/\/$/, '');

export async function list(resource: string) {
    const cleanResource = resource.replace(/\/$/, ''); // Remove trailing slash
    const separator = cleanResource.includes('?') ? '&' : '?';
    const url = `${API_URL}/${cleanResource}${separator}format=json`;
    console.log('Fetching:', url);
    const response = await fetch(url);
    console.log('Response status:', response.status);
    console.log('Response headers:', Object.fromEntries(response.headers.entries()));
    
    const text = await response.text();
    console.log('Response text (first 200 chars):', text.substring(0, 200));
    
    if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${text}`);
    }
    
    const data = JSON.parse(text);
    return data.results;
}

export async function get(resource: string, id: string) {
    const url = `${API_URL}/${resource}/${id}/?format=json`;
    console.log('Fetching:', url);
    const response = await fetch(url);
    console.log('Response status:', response.status);
    
    const text = await response.text();
    console.log('Response text (first 200 chars):', text.substring(0, 200));
    
    if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${text}`);
    }
    
    const data = JSON.parse(text);
    return data;
}
