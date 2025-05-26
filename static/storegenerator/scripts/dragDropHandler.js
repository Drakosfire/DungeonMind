import { lockTextareas, unlockTextareas, initializeTextareaResizing } from "./handleTextareas.js";
import { adjustPageLayout, getColumnFromOffset } from "./pageHandler.js";
import { buildBlock } from "./blockBuilder.js";
import { getState } from "./state.js";

export function handleDragStart(e) {
    lockTextareas();
    const target = e.target.closest('.block-item, .block-page');
    if (!target) {
        // console.error('Drag started for an element without a valid target');
        return;
    }
    const blockId = target.getAttribute('data-block-id');
    const pageId = target.getAttribute('data-page-id');
    if (!blockId) {
        // console.error('Drag started for an element without a data-block-id');
        return;
    }
    if (!pageId) {
        // console.error('Drag started for an element without a data-page-id');
        return;
    }
    
    // Store the block ID and inner HTML in the data transfer object
    const innerHTML = target.innerHTML;
    e.dataTransfer.setData('data-block-id', blockId);
    e.dataTransfer.setData('text/plain', innerHTML); // Store inner HTML
    e.dataTransfer.setData('data-page-id', pageId); // Store original page ID
    e.dataTransfer.effectAllowed = 'move';
    target.style.opacity = '0.4';

    // Create an invisible drag image
    const dragImage = document.createElement('div');
    dragImage.style.width = '1px';
    dragImage.style.height = '1px';
    dragImage.style.opacity = '0';
    document.body.appendChild(dragImage);
    e.dataTransfer.setDragImage(dragImage, 0, 0);

    // console.log(`Drag started for block ID: ${blockId} page ID: ${pageId}`);
}

export function handleDragEnd(e) {
    const target = e.target.closest('.block-item, .block-page');
    if (target) {
        target.style.opacity = '1'; // Reset the opacity
        const blockId = target.getAttribute('data-block-id');
        // console.log(`Drag ended for block ID: ${blockId}`);
    }

    // Remove highlight classes from pages and blocks
    document.querySelectorAll('.highlight-page').forEach(el => el.classList.remove('highlight-page'));
    document.querySelectorAll('.highlight-block').forEach(el => el.classList.remove('highlight-block'));
    document.querySelectorAll('.highlight-block-top').forEach(el => el.classList.remove('highlight-block-top'));
    unlockTextareas()

}

export function handleDragOver(e) {
    e.preventDefault();
    if (e.target.tagName === 'TEXTAREA' || e.target.closest('.block-item')) {
        e.dataTransfer.dropEffect = 'none'; // Indicate that drop is not allowed
        return;
    }
    e.dataTransfer.dropEffect = 'move'; // Indicate that drop is allowed

    const targetPage = e.target.closest('.page');
    if (targetPage) {
        targetPage.classList.add('highlight-page'); // Add highlight class for pages                
        }

    const targetBlock = e.target.closest('.block-item, .block-page');
    if (targetBlock) {
        const bounding = targetBlock.getBoundingClientRect();
        const offset = e.clientY - bounding.top;
        if (offset > bounding.height / 2) {
            targetBlock.classList.add('highlight-block');
            targetBlock.classList.remove('highlight-block-top');
        } else {
            targetBlock.classList.add('highlight-block-top');
            targetBlock.classList.remove('highlight-block');
        }
    }
}

export function handleDrop(e, elements) {
    let state = getState();
    e.preventDefault();
    // Ensure we are not dropping into a textarea or another block
    if (e.target.classList.contains('block-item', 'block-page', 'description-textarea') || e.target.tagName === 'TEXTAREA') {
        // console.log('Cannot drop block inside another block or textarea');
        return;
    }
    const blockId = e.dataTransfer.getData('data-block-id');
    const originalPageId = e.dataTransfer.getData('data-page-id');

    if (blockId && originalPageId) {
        const originalBlock = document.querySelector(`[data-block-id="${blockId}"]`);
        const newPage = e.target.closest('.page');
        // console.log(`Over page ${newPage} from page ID: ${originalPageId}`);
        const newPageId = newPage.getAttribute('data-page-id');
        
        // Ensure the original block exists before proceeding
        if (!originalBlock || !newPage) {
            // console.error(`Block with ID ${blockId} on page ${originalPageId} not found`);
            
            return;
        }   
        let newBlockContent;
        if (state.jsonData.storeData[blockId]) {
            // console.log('state.jsonData.storeData[blockId]:', state.jsonData.storeData[blockId]);
            newBlockContent = buildBlock(state.jsonData.storeData[blockId], blockId);
            if (newBlockContent) {
                newBlockContent.setAttribute('data-page-id', newPageId);
            } else {
                // console.error(`Failed to build block for blockId: ${blockId}`);
            }
        } else {
            // console.error(`No data found for blockId: ${blockId}`);
        }
        const target = e.target.closest('.block-item, .block-page');
        // console.log('target:', target);
        let targetColumn = 1;
        if (target) {
            const bounding = target.getBoundingClientRect();
            const offset = e.clientY - bounding.top;

            // console.log('Drop target found:', target);
            // console.log('Bounding rectangle:', bounding);
            // console.log('Offset from top:', offset);
            // console.log('Target height:', bounding.height);
            // console.log('Insert before or after decision point (height / 2):', bounding.height / 2);

            targetColumn = getColumnFromOffset(target, offset);
            if (offset > bounding.height / 2) {
                // console.log('Inserting after the target');
                target.parentNode.insertBefore(newBlockContent, target.nextSibling);
               
            } else {
                // console.log('Inserting before the target');
                target.parentNode.insertBefore(newBlockContent, target);
            }

            // Remove highlight borders
            target.style['border-bottom'] = '';
            target.style['border-top'] = '';
        } else {
            // console.log('No valid drop target found, appending to the end');
            newPage.querySelector('.block.monster.frame.wide').appendChild(newBlockContent);
        }

        // Remove the original block from the original container
        originalBlock.parentNode.removeChild(originalBlock);

        // Reset opacity of dragged element
        newBlockContent.style.opacity = '1';
        // console.log(`Moved existing block with ID: ${blockId} to page ID: ${newPageId}`);
        initializeTextareaResizing();
        // Adjust layouts
        if (originalPageId !== 'block-container') {
            adjustPageLayout(originalPageId, elements);
        }
        adjustPageLayout(newPageId, elements);
    } else {
        //console.log('No data transferred');
    }   
}

    
// export function handleDrop(e, elements) {
//     e.preventDefault();
//     // Ensure we are not dropping into a textarea or another block
//     if (e.target.classList.contains('block-item', 'block-page', 'description-textarea') || e.target.tagName === 'TEXTAREA') {
//         console.log('Cannot drop block inside another block or textarea');
//         return;
//     }
//     const blockId = e.dataTransfer.getData('block-id');
//     const originalPageId = e.dataTransfer.getData('data-page-id');
//     const innerHTML = e.dataTransfer.getData('text/plain');
//     console.log(`Drop event for block ID: ${blockId} from page ID: ${originalPageId}`);
    
//     if (blockId && originalPageId) {
//         const originalBlock = document.querySelector(`[data-block-id="${blockId}"]`);
//         const newPage = e.target.closest('.page');
//         console.log(`Over page ${newPage} from page ID: ${originalPageId}`);
//         const newPageId = newPage.getAttribute('data-page-id');
        
//         // Ensure the original block exists before proceeding
//         if (!originalBlock || !newPage) {
//             console.error(`Block with ID ${blockId} on page ${originalPageId} not found`);
            
//             return;
//         }

//         const newBlockContent = document.createElement('div');
//         newBlockContent.classList.add('block-page');
//         newBlockContent.innerHTML = originalBlock.innerHTML; // Transfer inner content only

//         // Add necessary attributes and event listeners
//         newBlockContent.setAttribute('data-block-id', blockId);
//         newBlockContent.setAttribute('data-page-id', newPageId);
//         console.log('newPageID:', newPageId);
//         newBlockContent.setAttribute('draggable', true);
//         newBlockContent.addEventListener('dragstart', handleDragStart);
//         newBlockContent.addEventListener('dragend', handleDragEnd);

//         const target = e.target.closest('.block-item, .block-page');
//         let targetColumn = 1;
//         if (target) {
//             const bounding = target.getBoundingClientRect();
//             const offset = e.clientY - bounding.top;

//             console.log('Drop target found:', target);
//             console.log('Bounding rectangle:', bounding);
//             console.log('Offset from top:', offset);
//             console.log('Target height:', bounding.height);
//             console.log('Insert before or after decision point (height / 2):', bounding.height / 2);

//             targetColumn = getColumnFromOffset(target, offset);
//             if (offset > bounding.height / 2) {
//                 console.log('Inserting after the target');
//                 target.parentNode.insertBefore(newBlockContent, target.nextSibling);
               
//             } else {
//                 console.log('Inserting before the target');
//                 target.parentNode.insertBefore(newBlockContent, target);
//             }

//             // Remove highlight borders
//             target.style['border-bottom'] = '';
//             target.style['border-top'] = '';
//         } else {
//             console.log('No valid drop target found, appending to the end');
//             newPage.querySelector('.block.monster.frame.wide').appendChild(newBlockContent);
//         }

//         // Remove the original block from the original container
//         originalBlock.parentNode.removeChild(originalBlock);

//         // Reset opacity of dragged element
//         newBlockContent.style.opacity = '1';
//         console.log(`Moved existing block with ID: ${blockId} to page ID: ${newPageId}`);
//         initializeTextareaResizing();
//         // Adjust layouts
//         if (originalPageId !== 'block-container') {
//             adjustPageLayout(originalPageId, elements);
//         }
//         adjustPageLayout(newPageId, elements);
//         } else {
//         console.log('No data transferred');
//     }
    
// }