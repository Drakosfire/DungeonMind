// domInit.js
import { updateState, getState } from './state.js';
import { buildElements } from './utils.js';
import { getConfig } from './config.js';



// Function to initialize and retrieve necessary DOM elements
export function initializeDOMElements() {
    const elements = buildElements();

    // Check for null elements and log errors
    for (const [key, value] of Object.entries(elements)) {
        if (!value) {
            console.error(`${key} element not found`);
        }
    }
    console.log('DOM elements initialized:', elements)

    return elements;
}

// Load JSON data from the server into the state as jsonData
export async function initialLoadJSON() {
    console.log('Loading JSON data from the server');
    try {
        // console.log('DUNGEONMIND_BASE_URL:', window.DUNGEONMIND_CONFIG.DUNGEONMIND_API_URL);
        const response = await fetch(`${window.DUNGEONMIND_CONFIG.DUNGEONMIND_API_URL}/static/root_store/Enchanted_Roots_Gear_Emporium/Enchanted_Roots_Gear_Emporium.json`);
        if (!response.ok) {
            throw new Error('Network response was not ok ' + response.statusText);
        }
        const data = await response.json();
        updateState('jsonData', data);
        console.log('State after updating jsonData:', getState().jsonData);
    }
    catch (error) {
        console.error('Template store not loaded into state:', error);
    }
}

