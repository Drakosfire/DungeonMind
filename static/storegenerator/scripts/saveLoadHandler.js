import { getState, updateState } from "./state.js";
import { initializeTextareaResizing } from "./handleTextareas.js";
import { iterateThroughBlocks } from "./jsonToBlocks.js";
import { clearBlocks } from "./utils.js";



// Function to save JSON data to the server
async function saveJson(dataToSend) {
    return fetch('/api/store/save-store', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(dataToSend)
    })
        .then(response => response.json())
        .then(data => {
            console.log('Success:', data);
            return data;
        })
        .catch((error) => {
            console.error('Error:', error);
        });
}

// Function to upload image to Cloudflare
async function uploadImageToCloudflare(image_url) {
    console.log('Uploading image:', image_url);
    try {
        const response = await fetch('/api/store/upload-image', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ image_url: image_url })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        console.log('Uploaded image:', data);
        return data; // Ensure the function returns the data
    } catch (error) {
        console.error('Error uploading image:', error);
        throw error; // Re-throw the error to handle it in the calling function
    }
}

// Main save handler
export async function saveHandler() {
    let state = getState();
    let jsonData = state.jsonData;
    console.log('JSON Data:', jsonData);
    let title = '';

    for (const blockId in jsonData.storeData) {
        console.log('Block ID:', blockId, 'Type:', jsonData.storeData[blockId].type);
        if (jsonData.storeData[blockId].type === 'title') {
            console.log('Title found:', jsonData.storeData[blockId].title);
            title = jsonData.storeData[blockId].title;
            break;
        }
    }
    // iterate through the blocks and upload the image to cloudflare
    for (const blockId in jsonData.storeData) {
        const block = jsonData.storeData[blockId];
        const { type, imgUrl, isNewImage } = block;

        // Check if the block should be processed
        if (type === 'image' && imgUrl && isNewImage) {
            console.log('New Image URL:', imgUrl);
            // upload the image to cloudflare
            let uploaded_image = await uploadImageToCloudflare(imgUrl);
            console.log('Uploaded image:', uploaded_image);
            // replace the image_url in the jsonData with the uploaded_image
            block.imgUrl = uploaded_image.image_url;
            // Remove the isNewImage flag after processing
            delete block.isNewImage;
        }
    }
    // Prepare data to send to the backend
    try {
        let dataToSend = jsonData;

        // Save the JSON data to the server
        await saveJson(dataToSend);
    } catch (error) {
        console.error('Error during save process:', error);
    }
    console.log('Saved JSON data:', jsonData);
    updateState('jsonData', jsonData.storeData);
    initializeSavedStoresDropdown();
}

// Function to ensure the blocks are in ascending order by ID
export function ensureAscendingOrder(blocks) {
    // console.log('Blocks before sorting:', blocks);
    // Convert block keys to array and sort by numeric portion of block-X
    const sortedKeys = Object.keys(blocks).sort((a, b) => {
        const numA = parseInt(a.split('-')[1]);
        const numB = parseInt(b.split('-')[1]);
        return numA - numB;
    });

    // Rebuild object with sorted keys
    const rebuiltBlocks = {};
    sortedKeys.forEach(key => {
        rebuiltBlocks[key] = blocks[key];
    });

    // console.log('Blocks after sorting:', rebuiltBlocks);
    return rebuiltBlocks;
}

// Function to load the store
export function loadHandler() {
    clearBlocks();
    let state = getState();
    // console.log('State:', state);
    let blocks = ensureAscendingOrder(state.jsonData.storeData);
    // console.log('jsonData:', state.jsonData);
    console.log('Blocks:', blocks);
    let ownerCount = 0;
    let employeeCount = 0;
    for (const [blockId, block] of Object.entries(blocks)) {
        if (block.type === 'owner') {
            ownerCount++;
        }
        if (block.type === 'employee') {
            employeeCount++;
        }
    }

    // Future feature: allow for indexing position on page

    // let blockIndex = 0;
    // for (const block of Object.values(pageBlocks)) {
    //     block['page-container-index'] = blockIndex++;
    // }

    iterateThroughBlocks(blocks, ownerCount, employeeCount);
    initializeTextareaResizing();
}

// Function to fetch the list of saved stores from the server
export async function fetchSavedStores() {
    try {
        const response = await fetch(`/api/store/list-saved-stores`);
        if (response.ok) {
            const data = await response.json();
            console.log('Fetched saved stores:', data);
            return data;
        } else if (response.status === 401) {
            console.log('User not logged in');
            return { stores: [], message: 'Please log in to view saved stores' };
        } else {
            console.error('Failed to fetch saved stores');
            return { stores: [], message: 'Failed to fetch saved stores' };
        }
    } catch (error) {
        console.error('Error fetching saved stores:', error);
        return { stores: [], message: 'Error fetching saved stores' };
    }
}

// Function to populate the dropdown with saved stores
function populateSavedStoresDropdown(data) {
    const dropdown = document.getElementById('savedStoresDropdown');
    const loadButton = document.getElementById('loadButton');
    dropdown.innerHTML = '';  // Clear any existing options

    if (data.stores && data.stores.length > 0) {
        data.stores.forEach((store) => {
            const option = document.createElement('option');
            option.value = store;
            option.textContent = store;  // Display the store name
            dropdown.appendChild(option);
        });
        dropdown.disabled = false;
        loadButton.disabled = false;
    } else {
        const option = document.createElement('option');
        option.value = "";
        option.textContent = data.message || "No saved stores available";
        dropdown.appendChild(option);
        dropdown.disabled = true;
        loadButton.disabled = true;
    }
    console.log('Dropdown populated:', dropdown);
}

// New function to initialize the dropdown
export async function initializeSavedStoresDropdown() {
    const data = await fetchSavedStores();
    populateSavedStoresDropdown(data);
}

// Modify loadSelectedStore to handle the case when no store is selected
export async function loadSelectedStore() {
    const dropdown = document.getElementById('savedStoresDropdown');
    const selectedStore = dropdown.value;  // Get the selected store's name
    console.log('Selected store:', selectedStore);

    if (selectedStore) {
        try {
            const response = await fetch(`/api/store/load-store?storeName=${encodeURIComponent(selectedStore)}`);
            if (response.ok) {
                console.log('Response:', response);
                const responseData = await response.json();
                console.log('Loaded response data:', responseData);
                updateState('jsonData', responseData);
                loadHandler();
            } else {
                console.error('Failed to load the store');
                alert('Failed to load the store. Please try again.');
            }
        } catch (error) {
            console.error('Error loading the store:', error);
            alert('Error loading the store. Please try again.');
        }
    } else {
        alert('Please select a store to load.');
    }
}





