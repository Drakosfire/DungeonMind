// main.js

import { initializeDOMElements, initialLoadJSON } from './domInit.js';
import { getState, updateState } from './state.js';
import { setupEventListeners } from './eventHandlers.js';
import { loadHandler } from './saveLoadHandler.js';
import { fetchLoadingImages } from './loadingImage.js';
import { getConfig } from './config.js';

// Function to check authentication status and update UI
async function checkAuthAndUpdateUI() {
    console.log('DUNGEONMIND_API_URL:', window.DUNGEONMIND_CONFIG.DUNGEONMIND_API_URL);
    try {
        const response = await fetch(`${window.DUNGEONMIND_CONFIG.DUNGEONMIND_API_URL}/auth/current-user`, {
            credentials: 'include'
        });
        if (response.ok) {
            const userData = await response.json();
            document.getElementById('loginButton').style.display = 'none';
            document.getElementById('logoutButton').style.display = 'inline-block';
            document.getElementById('saveButton').style.display = 'inline-block';
            document.getElementById('loadButton').style.display = 'inline-block';
            document.getElementById('savedStoresDropdown').style.display = 'inline-block';
        } else {
            console.log('User not authenticated');
            document.getElementById('loginButton').style.display = 'inline-block';
            document.getElementById('logoutButton').style.display = 'none';
            document.getElementById('saveButton').style.display = 'none';
            document.getElementById('loadButton').style.display = 'none';
            document.getElementById('savedStoresDropdown').style.display = 'none';
        }
    } catch (error) {
        console.error('Error checking authentication status:', error);
    }
}

document.addEventListener('DOMContentLoaded', async function () {
    try {
        // Fetch and store config globally on the window object
        console.log('Fetching config...');
        window.DUNGEONMIND_CONFIG = await getConfig();
        console.log('Config loaded:', window.DUNGEONMIND_CONFIG);

        // Initialize DOM elements
        await checkAuthAndUpdateUI();
        const elements = initializeDOMElements();
        if (!elements) {
            console.error('DOM initialization failed.');
            return;
        }

        // Set up initial state
        const state = getState();
        fetchLoadingImages();
        setupEventListeners(elements);

        // Wait for the JSON to load into the state
        await initialLoadJSON();

        // Call loadHandler after JSON is loaded
        loadHandler();
    } catch (error) {
        console.error('Initialization error:', error);
    }
});

