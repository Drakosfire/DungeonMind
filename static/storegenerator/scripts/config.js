/**
 * @typedef {Object} DungeonMindConfig
 * @property {string} DUNGEONMIND_API_URL - The base URL for the DungeonMind API
 */

/** 
 * Fetches the DungeonMind configuration
 * @returns {Promise<DungeonMindConfig>}
 */
async function getConfig() {
    try {
        const response = await fetch('/config');
        if (!response.ok) {
            throw new Error(`Failed to fetch config: ${response.statusText}`);
        }
        const config = await response.json();
        // console.log('Config loaded:', config); // Debug log
        return config;
    } catch (error) {
        console.error('Error fetching config:', error);
        throw error;
    }
}

export { getConfig };