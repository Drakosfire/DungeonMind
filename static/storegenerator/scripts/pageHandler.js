import { getState, updateState } from './state.js';
import { handleDragOver, handleDrop } from './dragDropHandler.js';

export function getColumnFromOffset(block, offset) {
    const page = block.closest('.page');
    if (!page) return 1;
    const columnWrapper = page.querySelector('.columnWrapper');
    const columnWrapperRect = columnWrapper.getBoundingClientRect();
    const relativeOffset = offset - columnWrapperRect.left; // Calculate the offset relative to the column wrapper
    const columnWidth = columnWrapper.clientWidth / 2; // Assuming two columns

    // Log details for debugging
    console.log('Block offset:', offset);
    console.log('Relative offset:', relativeOffset);

    const columnNumber = Math.ceil(relativeOffset / columnWidth);

    // Ensure the column number is within valid bounds (1 or 2)
    const validColumnNumber = Math.min(Math.max(columnNumber, 1), 2);


    return validColumnNumber;
}


// Function to get the height of a column by index
export function getColumnHeights(pageElement, elements) {
    const columns = [0, 0]; // Assuming two columns for simplicity
    const blocks = pageElement.querySelectorAll('.block-page');
    blocks.forEach(block => {
        const column = getColumnFromOffset(block, block.getBoundingClientRect().left, elements);
        columns[column - 1] += block.offsetHeight;
    });
    return columns;
}

export function adjustPageLayout(pageId, elements) {
    const state = getState();
    const page = document.querySelector(`[data-page-id="${pageId}"]`);
    if (!page) {
        console.error(`Page with ID ${pageId} not found`);
        return;
    }

    const columnHeights = getColumnHeights(page, elements);
    console.log(`Total height of columns in ${pageId}: ${columnHeights}`);

    for (let i = 0; i < columnHeights.length; i++) {
        if (columnHeights[i] > state.MAX_COLUMN_HEIGHT) {
            console.log(`Column ${i + 1} in ${pageId} exceeds max height, total height: ${columnHeights[i]}px`);
            handleColumnOverflow(page, i + 1, elements);
        }
    }
}

let pageCounter = 1;
// Function to create new page
export function addPage(elements) {
    const newPage = document.createElement('div');
    newPage.classList.add('page');
    newPage.setAttribute('data-page-id', `page-${pageCounter}`);
    newPage.id = `page-${pageCounter}`;

    const columnWrapper = document.createElement('div');
    columnWrapper.classList.add('columnWrapper');

    const newMonsterFrame = document.createElement('div');
    newMonsterFrame.classList.add('block', 'monster', 'frame', 'wide');

    columnWrapper.appendChild(newMonsterFrame);
    newPage.appendChild(columnWrapper);
    elements.pageContainer.appendChild(newPage);

    let currentPage = pageContainer.querySelector('.block.monster.frame.wide');

    currentPage = newMonsterFrame;
    console.log(`Created new page with ID: ${newPage.id}`);

    // Add event listeners to the new currentPage
    currentPage.addEventListener('dragover', handleDragOver);
    currentPage.addEventListener('drop', handleDrop);

    pageCounter++;
    return newPage;
}

export function removePage(elements) {
    const pages = elements.pageContainer.querySelectorAll('.page');

    if (pages.length > 1) { // Ensure at least one page remains
        const lastPage = pages[pages.length - 1];
        const blocks = lastPage.querySelectorAll('.block-page'); // Check for blocks inside the last page

        if (blocks.length > 0) {
            // If blocks are present, block the removal and display a warning
            console.log(`Cannot remove page with ID: ${lastPage.id} because it contains ${blocks.length} block(s).`);
            alert(`Cannot remove this page because it contains ${blocks.length} block(s). Please remove the blocks first.`);
        } else {
            // If no blocks are present, allow removal
            elements.pageContainer.removeChild(lastPage);
            console.log(`Page removed with ID: ${lastPage.id}`);
        }
    } else {
        alert(`Cannot remove this page because it is the only page.`);
        console.log('Cannot remove the last page.');
    }
}

export function handleColumnOverflow(page, targetColumn, elements) {
    const state = getState();
    console.log(`Handling overflow for page ID: ${page.getAttribute('data-page-id')} in column ${targetColumn}`);
    const blocks = Array.from(page.querySelectorAll('.block-page'));
    let columnHeights = [0, 0];
    let overflowStartIndex = -1;

    // Find the start index where overflow begins in the target column
    blocks.forEach((block, index) => {
        const column = getColumnFromOffset(block, block.getBoundingClientRect().left);
        columnHeights[column - 1] += block.offsetHeight;
        if (column === 2 && columnHeights[1] > state.MAX_COLUMN_HEIGHT && overflowStartIndex === -1) {
            overflowStartIndex = index;
        }
    });

    // If no overflow, return early
    if (overflowStartIndex === -1) {
        return;
    }
    const overflowBlocks = blocks.slice(overflowStartIndex);
    const overflowHeight = overflowBlocks.reduce((acc, block) => acc + block.offsetHeight, 0);

    // Get the next page if it exists
    const nextPage = getNextPage(page);
    if (nextPage) {
        const nextPageBlocks = nextPage.querySelectorAll('.block-page, .block-item');
        let nextPageColumnHeights = [0, 0];

        nextPageBlocks.forEach(block => {
            const column = getColumnFromOffset(block, block.getBoundingClientRect().left);
            nextPageColumnHeights[column - 1] += block.offsetHeight;
        });

        // Check if there's enough space in the target column of the next page
        if (nextPageColumnHeights[targetColumn - 1] + overflowHeight <= state.MAX_COLUMN_HEIGHT) {
            const nextPageContainer = nextPage.querySelector('.block.monster.frame.wide');
            overflowBlocks.forEach(block => {
                nextPageContainer.appendChild(block);
                block.setAttribute('data-page-id', nextPage.getAttribute('data-page-id'));
            });
            return;
        }
    }

    // Otherwise, create a new page and move the overflowing blocks there
    const newPage = addPage(elements);
    if (!newPage) {
        console.error('Failed to create a new page');
        return;
    }
    const newMonsterFrame = newPage.querySelector('.block.monster.frame.wide');
    if (!newMonsterFrame) {
        console.error('New monster frame not found in the new page');
        return;
    }

    overflowBlocks.forEach(block => {
        newMonsterFrame.appendChild(block);
        block.setAttribute('data-page-id', newPage.getAttribute('data-page-id'));
    });
    console.log(`Moved overflowing blocks to new page with ID: ${newPage.getAttribute('data-page-id')}`);
}

// Utility function to get the next page element
export function getNextPage(currentPage) {
    const nextPageId = parseInt(currentPage.getAttribute('data-page-id').split('-')[1]) + 1;
    return document.querySelector(`[data-page-id="page-${nextPageId}"]`);
}