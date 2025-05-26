import { getState } from './state.js';
import { addPage } from './pageHandler.js';
import { initializeTextareaResizing } from './handleTextareas.js';
import { loadHandler } from './saveLoadHandler.js';
import { autofillBlocks } from './blockHandler.js';

export function handleReset(elements) {
    console.log('Reset button clicked');
    const state = getState();
    // Clear blockContainer before reinserting blocks
    let blockPage = document.getElementById('block-page');
    console.log('blockPage:', blockPage);
    blockPage.innerHTML = '';
    console.log('Current initial positions:', state.initialPositions);
    loadHandler();

    // Remove all pages except the first one
    let pageContainer = document.getElementById('pages');
    let pages = pageContainer.querySelectorAll('.page');
    console.log('Pages:', pages);
    pages.forEach(page => {
        page.remove();
    }
    );
    let currentPage = pageContainer.querySelector('.page');
    console.log('Current page:', currentPage);
    // If no existing page is found, create the first page
    if (!currentPage) {
        currentPage = addPage(elements);
        currentPage.setAttribute('data-page-id', 'page-0');
        console.log('No existing pages found. Created the first page:', currentPage.id);
    }
    // 


    console.log('Reset complete, all blocks moved back to block-container');
    initializeTextareaResizing();
}

export function printScreen() {
    window.print()
}
// function to clear all blocks to prepare for a load
export function clearBlocks() {
    let blockPage = document.getElementById('block-page');
    blockPage.innerHTML = '';
    console.log('Block page cleared');
    // Remove all pages except the first one
    let pageContainer = document.getElementById('pages');
    let pages = pageContainer.querySelectorAll('.page');
    console.log('Pages:', pages);
    pages.forEach(page => {
        page.remove();
    }
    );
    let currentPage = pageContainer.querySelector('.page');
    console.log('Current page:', currentPage);
    // If no existing page is found, create the first page
    const elements = buildElements();
    if (!currentPage) {
        currentPage = addPage(elements);
        currentPage.setAttribute('data-page-id', 'page-0');
        console.log('No existing pages found. Created the first page:', currentPage.id);
    }
}

export function buildElements() {
    const elements = {};
    elements.blockContainer = document.getElementById('blockContainer');
    elements.blockContainerPage = document.getElementById('block-page');
    elements.pageContainer = document.getElementById('pages');
    elements.trashArea = document.getElementById('trashArea');
    elements.currentPage = elements.pageContainer ? elements.pageContainer.querySelector('.block.monster.frame.wide') : null;
    elements.modal = document.getElementById('imageModal');
    elements.modalImg = document.getElementById('modalImage');
    elements.captionText = document.getElementById('caption');
    elements.closeModal = document.getElementsByClassName('close')[0];
    elements.loadingImage = document.getElementById('loadingImage');
    return elements;
}

export function captureStoreHTML() {
    // Run autofill if there is a blank page without any blocks
    const elements = buildElements();
    if (elements.pageContainer.querySelector('.page') && !elements.blockContainer.querySelector('.block-item')) {
        autofillBlocks(elements);
    }
    console.log('Capturing store HTML');
    const brewRenderer = document.getElementById('brewRenderer');
    const contentClone = brewRenderer.cloneNode(true);

    // Find and remove all textareas and buttons
    const textareas = contentClone.querySelectorAll('.image-textarea');
    const buttons = contentClone.querySelectorAll('.generate-image-button');

    console.log('Found textareas:', textareas.length);
    console.log('Found buttons:', buttons.length);

    // Remove elements instead of just hiding them
    textareas.forEach(textarea => {
        textarea.remove();
        console.log('Removed textarea');
    });

    buttons.forEach(button => {
        button.remove();
        console.log('Removed button');
    });

    const htmlContent = `
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link href="https://www.dungeonmind.net/static/storegenerator/css/all.css" rel="stylesheet">
    <link href="https://www.dungeonmind.net/static/storegenerator/css/css.css?family=Open+Sans:400,300,600,700" rel="stylesheet">
    <link href="https://www.dungeonmind.net/static/storegenerator/css/bundle.css" rel="stylesheet">
    <link href="https://www.dungeonmind.net/static/storegenerator/css/style.css" rel="stylesheet">
    <link href="https://www.dungeonmind.net/static/storegenerator/css/5ePHBstyle.css" rel="stylesheet">
    <link href="https://www.dungeonmind.net/static/storegenerator/css/storeUI.css" rel="stylesheet">
</head>
<body>
    ${contentClone.outerHTML}
</body>
</html>`;

    return htmlContent;
}

export async function shareStore() {
    const htmlContent = captureStoreHTML();

    try {
        const response = await fetch('/api/store/share-store', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                html: htmlContent
            })
        });

        if (!response.ok) throw new Error('Failed to share store');
        const data = await response.json();
        console.log('Share URL:', data.share_url);

        // Show custom modal instead of alert
        showShareModal(data.share_url);
    } catch (error) {
        console.error('Error sharing store:', error);
        throw error;
    }
}

function showShareModal(url) {
    // Create modal HTML
    const modalHtml = `
        <div id="shareModal" class="share-modal">
            <div class="share-modal-content">
                <h3>Share Link</h3>
                <div class="url-container">
                    <input type="text" value="${url}" readonly id="shareUrl">
                    <button onclick="navigator.clipboard.writeText('${url}').then(() => this.textContent = 'Copied!').catch(() => alert('Failed to copy'))">
                        Copy
                    </button>
                </div>
                <button onclick="document.getElementById('shareModal').remove()">Close</button>
            </div>
        </div>
    `;

    // Add modal to page
    document.body.insertAdjacentHTML('beforeend', modalHtml);
}


