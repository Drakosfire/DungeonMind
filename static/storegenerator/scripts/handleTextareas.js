//handleTextareas.js
import { getState, updateState } from './state.js';

export function adjustTextareaHeight(el, offset = 0) {
    if (el.classList.contains('description-textarea')) {
        return;
    }
    // console.log('Adjusting height for:', el.id, 'Class List:', el.classList); // Debugging line
    if (el.scrollHeight > 20) {
        el.style.height = 'auto';
        el.style.height = (el.scrollHeight + offset) + 'px';
    }
    // console.log('New Height:', el.style.height); // Debugging line
}

export function initializeTextareaResizing() {
    const classes = [
        'description-textarea',
        'heading-textarea',
        'image-textarea',
        'properties-textarea',
        'string-action-description-textarea',
        'string-stat-textarea',
        'subtitle-textarea',
        'title-textarea',
        'user-description-textarea',
    ];
    let offset;  // Declare offset here

    classes.forEach(className => {
        if (className === 'description-textarea') {
            // console.log('Class is ', className, 'offset is 10');
            offset = 10;
        } else {
            offset = 0;
        }

        // console.log('Initializing textareas for class:', className);
        // console.log(document.querySelectorAll(`.${className}`));
        const textareas = document.querySelectorAll(`.${className}`);
        textareas.forEach(textarea => {
            // console.log('Textarea found:', textarea);                                          

            // Adjust height on page load
            adjustTextareaHeight(textarea, offset);
            // Adjust height on input
            textarea.addEventListener('input', function () {
                adjustTextareaHeight(textarea);
            });
            textarea.addEventListener('input', (event) => {
                let parentBlock = event.target.closest('.block-item') !== null ? event.target.closest('.block-item') : event.target.closest('.block-page'); // Find the closest parent with class 'block-item'
                // console.log('Parent block:', parentBlock);
                if (parentBlock) {
                    let blockId = parentBlock.getAttribute('data-block-id');
                    // console.log('Block ID:', blockId);
                    let pageId = parentBlock.getAttribute('data-page-id');
                    // console.log('Page ID:', pageId);
                    let property = event.target.getAttribute('data-property'); // Get property directly from textarea or div
                    handleInputChange(event, blockId, pageId, property);
                } else {
                    // console.error('Could not find parent block element');
                }
            });
        });
    });
}

function handleInputChange(event, blockId, pageId, property) {
    // Log the event details
    // console.log('Input change detected:', event.target);
    // console.log('Page ID:', pageId);
    // console.log('Block ID:', blockId);
    // console.log('Property being updated:', property);

    let state = getState();
    // console.log('State before update:', state.jsonData);
    // console.log('State before update:', state.jsonData[blockId][property]);
    let block = state.jsonData[blockId];
    // console.log('Block:', block);
    // console.log('Block property:', block[property]);
    block[property] = event.target.value !== undefined ? event.target.value : event.target.textContent;
    updateState('jsonData', state.jsonData);
    // console.log('State after update:', state.jsonData[blockId][property]);
}

export function lockTextareas() {
    const textareas = document.querySelectorAll('textarea');

    textareas.forEach(textarea => {
        textarea.setAttribute('disabled', true);
    });

    const descriptionTextareas = document.querySelectorAll('.description-textarea');

    descriptionTextareas.forEach(descriptionTextarea => {
        descriptionTextarea.removeAttribute('contenteditable');
    });

    // console.log('All textareas have been locked.');
}

export function unlockTextareas() {
    const textareas = document.querySelectorAll('textarea');

    textareas.forEach(textarea => {
        textarea.removeAttribute('disabled');
    });

    const descriptionTextareas = document.querySelectorAll('.description-textarea');

    descriptionTextareas.forEach(descriptionTextarea => {
        descriptionTextarea.setAttribute('contenteditable', 'true');
    });

    //console.log('All textareas have been unlocked.');
}

