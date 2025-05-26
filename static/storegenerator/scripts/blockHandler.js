import { getState } from './state.js';
import { handleDragStart, handleDragEnd } from './dragDropHandler.js';
import { initializeTextareaResizing } from './handleTextareas.js';
import { adjustPageLayout, addPage } from './pageHandler.js';
import { finishBlockProcessing } from './blockBuilder.js';

const state = getState();

export function toggleAllTextBlocks() {
    const pageContainer = document.querySelector('.page-container');
    const textareas = pageContainer.querySelectorAll('.image-textarea');
    const generateButtons = pageContainer.querySelectorAll('.generate-image-button');

    let isAnyVisible = Array.from(textareas).some(textarea => textarea.style.display === 'block');

    if (isAnyVisible) {
        // Hide all textareas and buttons
        textareas.forEach(textarea => textarea.style.display = 'none');
        generateButtons.forEach(btn => btn.style.display = 'none');
    } else {
        // Show all textareas and buttons
        textareas.forEach(textarea => textarea.style.display = 'block');
        generateButtons.forEach(btn => btn.style.display = 'inline-block');
        
    }
}

export function autofillBlocks(elements) {
    console.log('Autofill button clicked');

    const blocks = Array.from(blockContainer.querySelectorAll('.block-item'));
    let currentPage = elements.pageContainer.querySelector('.page'); 
    console.log('Current page:', currentPage);
    
    // If no existing page is found, create the first page
    if (!currentPage) {
        currentPage = addPage(elements);
        // console.log('No existing pages found. Created the first page:', currentPage.id);
    }
    console.log('Current page:', currentPage);
    // Iterate over each block and move it to the pageContainer
    blocks.forEach(block => {
        block.setAttribute('class', 'block-page');
        block.setAttribute('data-page-id', currentPage.getAttribute('data-page-id'));
        // Append the block to the current page's columnWrapper
        const newPage = currentPage.querySelector('.block.monster.frame.wide');
        newPage.appendChild(block);
        console.log(`Moved block with ID: ${block.getAttribute('data-block-id')} to page with ID: ${currentPage.getAttribute('data-page-id')}`);
        // Adjust the layout after adding the block; this function handles creating a new page if needed
        adjustPageLayout(currentPage.getAttribute('data-page-id'), elements);

        // Check if a new page was created and update curtrrentPage accordingly
        const lastPageInContainer = pageContainer.querySelector('.page:last-child');
        if (lastPageInContainer !== currentPage) {
            currentPage = lastPageInContainer;
            console.log('Moved to a new page:', currentPage.getAttribute('data-page-id'));            
        }
    });
    initializeTextareaResizing();
console.log('Autofill complete, all blocks moved to page-container');
}

// Store initial positions of the blocks
export function storeInitialPositions(blockContainer) {
    const blocks = blockContainer.querySelectorAll('.block-item');
    blocks.forEach((block, index) => {
        const blockId = block.getAttribute('data-block-id');
        if (!blockId) {
            console.error(`Block at index ${index} is missing data-block-id`);
        }
        state.initialPositions.push({
            id: blockId,
            index: index
        });
    });
    console.log('Initial positions:', state.initialPositions);
}

export function sortBlocksById(blockContainerPage) {
    // Select all blocks inside the block-container
    const blocks = Array.from(blockContainerPage.querySelectorAll('.block-item'));
    // console.log('Initial Blocks in blockContainerPage:', blocks);

    // Sort the blocks based on the numeric portion of their block-id attribute
    blocks.sort((a, b) => {
        // Extract the numeric part of the block-id (e.g., 'block-1' -> 1)
        const idA = parseInt(a.getAttribute('data-block-id').match(/\d+/), 10);
        const idB = parseInt(b.getAttribute('data-block-id').match(/\d+/), 10);
        // console.log('Comparing:', idA, idB);
        return idA - idB; // Ascending order
    });

    // Log the IDs after sorting
    blocks.forEach(block => {
        // console.log('Block ID after sorting:', block.getAttribute('data-block-id'));
    });

    // Clear the block-container before re-appending the sorted blocks
    blockContainerPage.innerHTML = '';
    blocks.forEach(block => {
        blockContainerPage.appendChild(block);
        // Re-attach event listeners to the block here
        finishBlockProcessing(block);
    });

    // Re-append the blocks in the sorted order
    blocks.forEach(block => blockContainerPage.appendChild(block));

    console.log('Blocks have been sorted and re-appended based on block-id');
    console.log('Contents of blockContainerPage', blockContainerPage);
}


export function insertHtmlBlocks(blocks, elements) {
    // console.log('blockContainerPage = ', elements.blockContainerPage)
    // console.log('List of blocks:', blocks);
    const parser = new DOMParser();
    
    blocks.forEach(blockHtml => {
        console.log('Original blockHtml:', blockHtml);
        // Parse the HTML string
        const doc = parser.parseFromString(blockHtml, 'text/html');
        const block = doc.body.firstChild;
        if (block) {
            elements.blockContainerPage.appendChild(block); // Append the parsed block to the container
            console.log('Appended block:', block);
        }
    });
    // console.log('Final state of blockContainer:', blockContainer.innerHTML);
    initializeTextareaResizing();
}

export async function extractBlocks(elements) {
    const { blockContainerPage } = elements; // Destructure the necessary DOM elements
    const { blockContainer } = elements;
    try {
        if (blockContainerPage.children.length > 1) {
            console.log('Blocks already loaded, skipping fetch');
            return;
        }
        
        const response = await fetch('./static/template_update.html');
        if (!response.ok) {
            throw new Error('Network response was not ok ' + response.statusText);
        }
        
        const text = await response.text();
        const parser = new DOMParser();
        const doc = parser.parseFromString(text, 'text/html');
        
        // Selecting all elements with the 'block-item' class
        const blocks = doc.querySelectorAll('.block-item');
        
        blocks.forEach((block, index) => {
            const blockContent = block.innerHTML;            
            const blockItem = document.createElement('div');
            blockItem.classList.add('block-item');
            blockItem.innerHTML = blockContent;
            
            // Assigning unique block ID
            const blockId = `block-${index}`;
            blockItem.setAttribute('data-block-id', blockId);
            
            // Setting the page ID and other attributes
            const pageId = 'block-container';
            blockItem.setAttribute('data-page-id', pageId);
            blockItem.setAttribute('draggable', true);

            // Set block type
            const blockType = block.getAttribute("type")
            blockItem.setAttribute('type', blockType)
            
            // Add event listeners for drag and drop functionality
            blockItem.addEventListener('dragstart', handleDragStart);
            blockItem.addEventListener('dragend', handleDragEnd);
            
            console.log(`Loaded block with ID: ${blockId}`);
            
            // Append block to the container
            blockContainerPage.appendChild(blockItem);
        });
        
        // Store the initial positions of the blocks (if needed for drag and drop)
        storeInitialPositions(blockContainer);
        
    } catch (error) {
        console.error('Error fetching and parsing template_update.html:', error);
    }
    initializeTextareaResizing();
}

