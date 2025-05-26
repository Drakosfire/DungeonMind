import { handleDragStart, handleDragEnd } from "./dragDropHandler.js";

// iterate through container blocks, identify their type, and build the html
export function buildBlock(block, blockId) {
    const allBlocks = document.querySelectorAll('[data-block-id]');
    const ownerCount = Array.from(allBlocks).filter(block => { return block.getAttribute('type') === 'owner'; }).length
    const employeeCount = Array.from(allBlocks).filter(block => { return block.getAttribute('type') === 'employee'; }).length


    // Define a mapping of block types to IDs and logic
    const blockTypeMap = {
        'title': (block, blockId) => buildTitleBlock(block, blockId),
        'image': (block, blockId) => buildImageBlock(block, blockId),
        'store-properties': (block, blockId) => buildStorePropertiesBlock(block, blockId),
        'owner': (block, blockId) => buildOwnerBlock(block, blockId, ownerCount, block.ownerId),
        'employee': (block, blockId) => buildEmployeeBlock(block, blockId, employeeCount, block.employeeId),
        'customers': (block, blockId) => buildEntryBlock('customers', block, blockId, block.customerId),
        'quests': (block, blockId) => buildEntryBlock('quests', block, blockId, block.questsId),
        'services': (block, blockId) => buildEntryBlock('services', block, blockId, block.servicesId),
        'specialties': (block, blockId) => buildEntryBlock('specialties', block, blockId, block.specialtiesId),
        'security': (block, blockId) => buildEntryBlock('security', block, blockId, block.securityId),
        'inventory': (block, blockId) => buildInventoryBlock(block, blockId)
    };



    if (blockTypeMap[block.type]) {
        const dropBlock = blockTypeMap[block.type](block, blockId);  // Call the appropriate function
        return dropBlock;
    } else {
        console.log(`Unknown block type: ${block.type}`);
    }

}

export function finishBlockProcessing(block) {
    let newBlock;
    if (block instanceof HTMLElement && block.tagName.toLowerCase() === 'div') {
        newBlock = block;
    } else {
        newBlock = document.createElement('div');
        newBlock.innerHTML = block.trim();
        newBlock = newBlock.firstChild;
    }
    newBlock.addEventListener('dragstart', handleDragStart);
    newBlock.addEventListener('dragend', handleDragEnd);
    return newBlock;
}

// Helper function to format the keys for display purposes
function formatKeyToDisplay(key) {
    return key.replace('store', '').replace(/-/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}

// Take in a specific iterable type and iterable, and return the html for that iterable

export function processIterable(iterableType, iterable, blockId) {
    // console.log('Processing iterable:', iterable);

    let iterableHtml = `<tr>
        <td align="left"><strong>${formatKeyToDisplay(iterableType)}</strong></td>
        <td align="right"><textarea class="string-action-description-textarea" id="user-store-${iterableType}-${blockId}"
        hx-post="/update-stats" hx-trigger="change" hx-target="#user-store-${iterableType}-${blockId}t" hx-swap="outerHTML"
        title="${formatKeyToDisplay(iterableType)}">${iterable.join(', ')}</textarea></td>
    </tr>`;

    return iterableHtml;
}

export function buildTitleBlock(block, blockId) {
    let titleBlockHtml = `<div class="block-item" type="title" data-block-id = ${blockId} data-page-id=${block.dataPageId} draggable="true"><h1>
    <textarea class="title-textarea" data-property="title" id="user-store-title" hx-swap="outerHTML" title="Name of store">${block.title}</textarea></h1>
    <div contenteditable="true" class="description-textarea" data-property="description" id="user-store-description"
        hx-post="/update-stats" hx-trigger="change"
        hx-target="#user-monster-description" hx-swap="outerHTML"
        title="Any amount or style of description">
       <p>${block.title} ${block.description} </p>
    </div> `;
    const newBlock = finishBlockProcessing(titleBlockHtml);
    return newBlock;
}

export function buildImageBlock(block, blockId) {

    // Prepend the DUNGEONMIND_API_URL to the image source if it's a relative URL
    const imageUrl = block.imgUrl && !block.imgUrl.startsWith('http')
        ? `${window.DUNGEONMIND_CONFIG.DUNGEONMIND_API_URL}${block.imgUrl}`
        : block.imgUrl || '';

    let imageBlockHtml = `
    <div class="block-item" type="image" data-block-id="${blockId}" data-page-id="${block.dataPageId}" draggable="true">
        <img id="generated-image-${blockId}" alt="" src="${imageUrl}" class="store-image" style="cursor: pointer; ${imageUrl ? '' : 'display: none;'}">
        <textarea class="image-textarea" data-property="sdprompt" id="sd-prompt-${blockId}" hx-post="/update-stats" hx-trigger="change" hx-target="#user-store-image" hx-swap="outerHTML" title="Store Image">${block.sdprompt || ''}</textarea>
        <button class="generate-image-button" data-block-id="${blockId}">
            <img src="https://imagedelivery.net/SahcvrNe_-ej4lTB6vsAZA/f0bbc7ea-5c80-437d-b98c-6611fd15e400/public" alt="Generate Image">
        </button>        
    </div>`;
    const newBlock = finishBlockProcessing(imageBlockHtml);
    return newBlock;
}

export function buildStorePropertiesBlock(block, blockId) {
    let storePropertiesBlockHtmlStart = `
    <div class="block-item" type="store-properties" data-block-id=${blockId} data-page-id=${block.dataPageId} draggable="true">
    <div class="block classTable frame decoration">
        <table>
            <thead>
                <tr>
                    <th align="left"></th>
                    <th align="center"></th>
                    <th align="center"></th>
                </tr>
            </thead>
            <tbody>`;

    for (let key in block) {
        if (Array.isArray(block[key])) {
            storePropertiesBlockHtmlStart += processIterable(key, block[key], blockId);
        } else if (key !== 'type' && key !== 'dataPageId') {
            storePropertiesBlockHtmlStart += `
                <tr>
                    <td align="left"><strong>${formatKeyToDisplay(key)}</strong></td>
                    <td align="right"><textarea class="string-action-description-textarea" data-property="${key}" id="user-store-${key}-${blockId}"
                  hx-post="/update-stats" hx-trigger="change" hx-target="#user-store-${key}-${blockId}t" hx-swap="outerHTML"
                  title="${key}">${block[key]}</textarea></td>
                </tr>`;
        }
    }

    let storePropertiesBlockHtmlEnd = `
            </tbody>
        </table>
    </div>
    </div>`;
    const storePropertiesBlockHtml = storePropertiesBlockHtmlStart + storePropertiesBlockHtmlEnd;
    const newBlock = finishBlockProcessing(storePropertiesBlockHtml);
    return newBlock;

}

function buildOwnerHeadingBlock(ownerCount) {
    if (ownerCount === 0) {
        return '';
    } else if (ownerCount === 1) {
        let ownerHeading = `<h2>Owner</h2>`;
        return ownerHeading;
    } else {
        let ownerHeading = `<h2>Owners</h2>`;
        return ownerHeading;
    }
}

function buildEmployeeHeadingBlock(employeeCount) {
    if (employeeCount === 0) {
        return '';
    } else if (employeeCount === 1) {
        let employeeHeading = `<h2>Employee</h2>`;
        return employeeHeading;
    } else {
        let employeeHeading = `<h2>Employees</h2>`;
        return employeeHeading;
    }
}
export function buildOwnerBlock(block, blockId, ownerCount, ownerId) {

    let ownerBlockHtml = `<div class="block-item" type="owner" ownerId =${ownerId} data-block-id=${blockId} data-page-id=${block.dataPageId} draggable="true">`;
    if (ownerId === 1) { ownerBlockHtml += buildOwnerHeadingBlock(ownerCount); }
    ownerBlockHtml += `<h3 id="owner-${ownerId}"><textarea class="subtitle-textarea" data-property="name" id="user-store-owner-${ownerId}"
                  hx-post="/update-stats" hx-trigger="change" hx-target="#user-store-owner-${ownerId}" hx-swap="outerHTML"
                  title="Owner Name">${block.name}</textarea></h3>`
    ownerBlockHtml += `<table>
                            <thead> 
                                <tr>
                                    <th align="center"></th>    
                                    <th align="center"></th>
                                </tr>
                            </thead>
                            <tbody>`;
    for (let key in block) {
        if (Array.isArray(block[key])) {
            ownerBlockHtml += processIterable(key, block[key], blockId);
        } else if (key !== 'type' && key !== 'dataPageId') {
            ownerBlockHtml += `<tr>
                <td align="left"><strong>${formatKeyToDisplay(key)}</strong></td>
                <td align="right"><textarea class="string-action-description-textarea" data-property="${key}" id="user-store-${key}-${blockId}"
              hx-post="/update-stats" hx-trigger="change" hx-target="user-store-${key}-${blockId}t" hx-swap="outerHTML"
              title="${key}">${block[key]}</textarea></td>
            </tr>`;
        }
    }
    const newBlock = finishBlockProcessing(ownerBlockHtml);
    return newBlock;
}

export function buildEmployeeBlock(block, blockId, employeeCount, employeeId) {

    let employeeBlockHtml = `<div class="block-item" type="employee" employeeId=${employeeId} data-block-id=${blockId} data-page-id=${block.dataPageId} draggable="true">`;
    if (employeeId === 1) { employeeBlockHtml += buildEmployeeHeadingBlock(employeeCount); }
    employeeBlockHtml += `<h3 id="employee-${employeeId}"><textarea class="subtitle-textarea" data-property="name" id="employee-${employeeId}"
                  hx-post="/update-stats" hx-trigger="change" hx-target="#employee-${employeeId}" hx-swap="outerHTML"
                  title="Employee Name">${block.name}</textarea></h3>`
    employeeBlockHtml += `<table>
                            <thead> 
                                <tr>
                                    <th align="center"></th>    
                                    <th align="center"></th>
                                </tr>
                            </thead>
                            <tbody>`;
    for (let key in block) {
        if (Array.isArray(block[key])) {
            EmployeeBlockHtml += processIterable(key, block[key], blockId);
        } else if (key !== 'type' && key !== 'dataPageId') {
            employeeBlockHtml += `<tr>
                <td align="left"><strong>${formatKeyToDisplay(key)}</strong></td>
                <td align="right"><textarea class="string-action-description-textarea" data-property="${key}" id="${key}-${blockId}"
                hx-post="/update-stats" hx-trigger="change" hx-target="#${key}-${blockId}" hx-swap="outerHTML"
                title="${key}">${block[key]}</textarea></td>
            </tr>`;
        }
    }
    const newBlock = finishBlockProcessing(employeeBlockHtml);
    return newBlock;
}
// Function to build a section block block in HTML
export function buildEntryBlock(section, block, blockId, entryId) {
    // console.log('Building entry block:', section, block, blockId, entryId);
    let sectionBlockHtml = '';
    // Begin the HTML block
    sectionBlockHtml += `<div class="block-item" type=${blockId} "${blockId}Id"=${entryId} data-block-id=${blockId} data-page-id=${block.dataPageId} draggable="true">`;
    // Add a section title if the entry_id is 1
    if (entryId === 1) {
        sectionBlockHtml += `<h1 id="store-${section}">${section}</h1>`;
    }
    // Iterate over the block features and generate HTML
    for (const feature in block) {
        if (block.hasOwnProperty(feature)) {
            if (feature !== 'type' && feature !== 'dataPageId') {
                if (feature === 'name') {
                    // Add a subtitle textarea for the name feature
                    sectionBlockHtml += `<h3 id="${section}-${entryId}">
                        <textarea class="subtitle-textarea" data-property="name" id="${section}-${entryId}"
                            hx-post="/update-stats" hx-trigger="change" hx-target="#${section}-${entryId}t" hx-swap="outerHTML"
                            title="${section}">${block['name']}</textarea>
                        </h3>`;
                } else {
                    // Add a description textarea for other features
                    let featureName = formatKeyToDisplay(feature); // Capitalize first letter
                    sectionBlockHtml += `<p>
                        <textarea class="string-action-description-textarea" data-property="${feature}" id="user-store-${section}-${blockId}"
                            hx-post="/update-stats" hx-trigger="change" hx-target="#user-store-${section}-${blockId}t" hx-swap="outerHTML"
                            title="${section}">${featureName}: ${block[feature]}</textarea>
                        </p>`;
                }
            }
        }
    }
    // End the HTML block
    sectionBlockHtml += `</div>`;
    const newBlock = finishBlockProcessing(sectionBlockHtml);
    // console.log(newBlock);
    return newBlock;
}
// Function to build the inventory block in HTML
export function buildInventoryBlock(block, blockId) {
    let inventoryBlockHtml = `<div class="block-item" data-block-id=${blockId} data-page-id=${block.dataPageId} draggable="true">
                                <div class="block classTable frame decoration">
                                    <h5 id="inventory">Inventory</h5>
                                    <table>
                                        <thead>
                                            <tr>
                                                <th align="center">Name</th>
                                                <th align="center">Type</th>
                                                <th align="center">Cost</th>
                                                <th align="center">Properties</th>
                                            </tr>
                                        </thead>
                                        <tbody>`;

    // Iterate through each inventory type
    const inventoryTypes = [
        "core_inventory",
        "weapons",
        "armor",
        "potions",
        "scrolls",
        "magical_items",
        "mundane_items",
        "miscellaneous_items"
    ];

    inventoryTypes.forEach(type => {
        let inventoryList = block[type];
        if (inventoryList && inventoryList.length > 0 && inventoryList[0].name !== "") {
            inventoryList.forEach((item, index) => {
                // Log the item and its properties before processing
                // console.log(`Processing item:`, item, `Index:`, index);
                // console.log(`item.properties:`, item.properties);

                // Ensure properties is an array
                let properties;
                if (Array.isArray(item.properties)) {
                    properties = item.properties.join(", ");
                } else {
                    // console.warn(`item.properties is not an array for item:`, item);
                    properties = item.properties; // Handle as a string or another type
                }

                // Log the processed properties
                // console.log(`Processed properties:`, properties);

                // Create the HTML for each inventory item
                inventoryBlockHtml += `<tr>
                                            <td align="center"><textarea class="string-action-description-textarea" data-property="${type}-${index}-name" id="user-store-item-name-${blockId}-${index}" hx-post="/update-stats"  title="Item Name">${item.name}</textarea></td>
                                            <td align="center"><textarea class="string-action-description-textarea" data-property="${type}-${index}-type" id="user-store-item-type-${blockId}-${index}" hx-post="/update-stats"  title="Item Type">${item.type}</textarea></td>
                                            <td align="center"><textarea class="string-action-description-textarea" data-property="${type}-${index}-cost" id="user-store-item-cost-${blockId}-${index}" hx-post="/update-stats"  title="Item Cost">${item.cost}</textarea></td>
                                            <td align="center"><textarea class="string-action-description-textarea" data-property="${type}-${index}-properties" id="user-store-item-properties-${blockId}-${index}"  title="Item Properties">${properties}</textarea></td>
                                        </tr>`;
            });
        }
    });


    // Close the HTML string
    inventoryBlockHtml += `</tbody>
                            </table>
                            </div> 
                        </div>`;

    // Return the constructed HTML block
    const newBlock = finishBlockProcessing(inventoryBlockHtml);
    // console.log(newBlock);
    return newBlock;

}




