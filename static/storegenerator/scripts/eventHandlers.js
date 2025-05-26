// eventHandlers.js
import { printScreen, handleReset, shareStore } from './utils.js';
import { addPage, removePage } from './pageHandler.js';
import {
    toggleAllTextBlocks,
    autofillBlocks,
    storeInitialPositions
} from './blockHandler.js';
import { startLoadingAnimation, stopLoadingAnimation } from './loadingImage.js';
import { handleDragOver, handleDrop, } from './dragDropHandler.js';
import { handleTrashOver, handleTrashDrop, handleTrashLeave } from './trashHandler.js';
import { getState, updateState, resetState } from './state.js';
import { loadHandler, saveHandler, fetchSavedStores } from './saveLoadHandler.js';
import { convertToBlockFormat } from './jsonToBlocks.js';
import { loadSelectedStore, initializeSavedStoresDropdown } from './saveLoadHandler.js';
import { getConfig } from './config.js';
import { preloadedLoadingGeneratedImage } from './loadingImage.js';

// Function to handle click events
export function handleClick(event, elements) {
    console.log('Click detected:', event.target);

    const videoModal = document.getElementById('videoModal');
    const closeVideo = document.getElementsByClassName('close-video')[0];

    // Check if user has seen the video
    function hasSeenVideo() {
        return document.cookie.split('; ').some(row => row.startsWith('hasSeenVideo='));
    }

    // Set cookie that user has seen the video
    function setVideoSeen() {
        document.cookie = 'hasSeenVideo=true; max-age=31536000; path=/'; // Expires in 1 year
    }

    // Show video if user hasn't seen it
    if (!hasSeenVideo()) {
        videoModal.style.display = 'block';
        setVideoSeen();
    }

    // Close modal when clicking X
    closeVideo.onclick = function () {
        videoModal.style.display = 'none';
    }

    // Close modal when clicking outside
    window.onclick = function (event) {
        if (event.target == videoModal) {
            videoModal.style.display = 'none';
        }
    }

    // Handle image clicks for modal display
    if (event.target.tagName === 'IMG' && event.target.id.startsWith('generated-image-')) {
        console.log('Image clicked for modal display. Image ID:', event.target.id);
        elements.modal.style.display = 'block';
        elements.modalImg.src = event.target.src;
        captionText.innerHTML = event.target.alt;
    }

    if (event.target.id === 'dungeonmindButton') {
        console.log('DungeonMind button clicked. Element ID:', event.target.id);
        // Redirect to the DUNGEONMIND_API_URL that is stored in the window object
        window.location.href = window.DUNGEONMIND_CONFIG.DUNGEONMIND_API_URL;
    }

    if (event.target.id === 'loginButton') {
        console.log('Login button clicked. Element ID:', event.target.id);
        window.location.href = '/auth/login';
    }

    if (event.target.id === 'logoutButton') {
        console.log('Logout button clicked. Element ID:', event.target.id);
        resetState();
        window.location.href = '/auth/logout';
    }
    // Handle modal close button
    if (event.target.id === 'closeModal') {
        // console.log('Close button clicked for modal. Element ID:', event.target.id);
        elements.modal.style.display = "none";
    }

    // Handle modal close when clicking outside of the modal content
    if (event.target === elements.modal) {
        // console.log('Clicked outside of modal content, closing modal.');
        elements.modal.style.display = "none";
    }
    // Handle print button click
    if (event.target.id === 'printButton') {
        // console.log('Print button clicked. Element ID:', event.target.id);
        printScreen();
    }

    // Handle share button click
    if (event.target.id === 'shareButton') {
        console.log('Share button clicked. Element ID:', event.target.id);
        shareStore();
    }

    // Handle generate image button click

    const button = event.target.closest('.generate-image-button');

    if (button) {
        const blockId = button.getAttribute('data-block-id');
        // console.log('Generate image button clicked. Block ID:', blockId);
        generateImage(blockId);
    }

    // Handle page add button
    if (event.target.id === 'addPageButton') {
        // console.log('Add page button clicked. Element ID:', event.target.id);
        addPage(elements);
    }

    // Handle page remove button
    if (event.target.id === 'removePageButton') {
        // console.log('Remove page button clicked. Element ID:', event.target.id);
        removePage(elements);
    }

    // Handle toggle button click
    if (event.target.id === 'toggleButton') {
        // console.log('Toggle button clicked. Element ID:', event.target.id);
        toggleAllTextBlocks();
    }

    // Handle autofill button click
    if (event.target.id === 'autofillButton') {
        // console.log('Autofill button clicked. Element ID:', event.target.id);
        autofillBlocks(elements);
    }

    // Handle reset button click
    if (event.target.id === 'resetButton') {
        // console.log('Reset button clicked. Element ID:', event.target.id);
        handleReset(elements);
    }

    // Handle reset button click
    if (event.target.id === 'saveButton') {
        saveHandler();
        // console.log('Save button clicked. Element ID:', event.target.id);
    }

    // Handle load button click
    if (event.target.id === 'loadButton') {
        // console.log('Load button clicked. Element ID:', event.target.id);
        loadSelectedStore();

    }

    if (event.target.id === 'tutorialButton') {
        console.log('Tutorial button clicked');
        const videoModal = document.getElementById('videoModal');
        const youtubeFrame = document.getElementById('youtubeFrame');

        // Reset video src to restart it
        const videoSrc = youtubeFrame.src;
        youtubeFrame.src = videoSrc;

        // Show modal
        videoModal.style.display = 'block';
    }

    if (event.target.id === 'submitButton') {
        let state = getState();
        // console.log('Submit description button clicked. Element ID:', event.target.id);
        const userInput = document.getElementById('user-description').value;
        elements.blockContainerPage.innerHTML = ''; // Clear the block container before inserting new blocks
        startLoadingAnimation();
        // console.log('State before:', state);


        fetch('/api/store/process-description', {

            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ user_input: userInput })
        })
            .then(response => response.json())
            .then(data => {
                // console.log('Success:', data);
                // Store the llm_output in the state for future use

                updateState('jsonData', convertToBlockFormat(data.llm_output));

                // console.log('State after:', state.jsonData);
                state.initialPositions.length = 0; // Clear the initialPositions array
                loadHandler();
                storeInitialPositions(elements.blockContainer);
            })
            .catch((error) => {
                // console.error('Error:', error);
            })
            .finally(() => {
                stopLoadingAnimation();
            });
    }
}

// Function to generate image
export function generateImage(blockId) {
    let state = getState();

    // Check if state.jsonData exists
    if (!state.jsonData) {
        return;
    }

    // Check if the blockId exists in jsonData
    let block = state.jsonData.storeData[blockId];
    if (!block) {
        return;
    }

    // Get the elements related to the block
    const sdPromptElement = document.getElementById(`sd-prompt-${blockId}`);
    const imageElement = document.getElementById(`generated-image-${blockId}`);

    // Check if the required elements exist
    if (!sdPromptElement || !imageElement) {
        return;
    }

    // Use the cached loading image
    imageElement.src = preloadedLoadingGeneratedImage.src;
    imageElement.style.display = 'block';

    // Get the prompt text
    const sdPrompt = sdPromptElement.value;

    // Proceed with generating the image
    fetch('/api/store/generate-image', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ sd_prompt: sdPrompt })
    })
        .then(response => {
            if (!response.ok) {
                throw new Error(`Server error: ${response.status} ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            if (!data.image_url) {
                throw new Error('Error: Image URL not found in the response.');
            }

            // Update the block and the image element
            block['imgUrl'] = data.image_url;
            block['isNewImage'] = true;
            imageElement.src = data.image_url;
        })
        .catch((error) => {
            // Handle errors
        });
}


export function setupEventListeners(elements) {
    // Click event listener
    document.addEventListener('click', (event) => handleClick(event, elements));
    // Event listeners for drag and drop functionality
    elements.blockContainer.addEventListener('dragover', handleDragOver);

    // Use an anonymous function to pass elements to handleDrop
    elements.blockContainer.addEventListener('drop', (event) => handleDrop(event, elements));
    elements.pageContainer.addEventListener('dragover', handleDragOver);
    elements.pageContainer.addEventListener('drop', (event) => handleDrop(event, elements));

    // Event listeners for trash area
    elements.trashArea.addEventListener('dragover', handleTrashOver);
    elements.trashArea.addEventListener('dragleave', handleTrashLeave);
    elements.trashArea.addEventListener('drop', (event) => handleTrashDrop(event, elements));

    // Add this line to initialize the dropdown when the page loads
    initializeSavedStoresDropdown();
}

