import {
    buildTitleBlock,
    buildImageBlock,
    buildStorePropertiesBlock,
    buildOwnerBlock,
    buildEmployeeBlock,
    buildEntryBlock,
    buildInventoryBlock
} from "./blockBuilder.js";

function appendBlockToDOM(newBlock, pageId) {
    // Find the page using pageId
    let pageContainer = document.querySelector(`[data-page-id=${pageId}]`);

    if (!pageContainer) {
        console.error(`Page with ID ${pageId} not found.`);
        return;
    }

    pageContainer.appendChild(newBlock);
}
// iterate through container blocks, identify their type, and build the html
export function iterateThroughBlocks(blocks, ownerCount, employeeCount) {
    let blockIDs = {
        ownerID: 1,
        employeeID: 1,
        customerID: 1,
        questID: 1,
        serviceID: 1,
        specialtyID: 1,
        securityID: 1
    };

    // Define a mapping of block types to IDs and logic
    const blockTypeMap = {
        'title': (block, blockId) => buildTitleBlock(block, blockId),
        'image': (block, blockId) => buildImageBlock(block, blockId),
        'store-properties': (block, blockId) => buildStorePropertiesBlock(block, blockId),
        'owner': (block, blockId) => buildOwnerBlock(block, blockId, ownerCount, blockIDs.ownerID++),
        'employee': (block, blockId) => buildEmployeeBlock(block, blockId, employeeCount, blockIDs.employeeID++),
        'customers': (block, blockId) => buildEntryBlock('customers', block, blockId, blockIDs.customerID++),
        'quests': (block, blockId) => buildEntryBlock('quests', block, blockId, blockIDs.questID++),
        'services': (block, blockId) => buildEntryBlock('services', block, blockId, blockIDs.serviceID++),
        'specialties': (block, blockId) => buildEntryBlock('specialties', block, blockId, blockIDs.specialtyID++),
        'security': (block, blockId) => buildEntryBlock('security', block, blockId, blockIDs.securityID++),
        'inventory': (block, blockId) => buildInventoryBlock(block, blockId)
    };

    for (const [blockId, block] of Object.entries(blocks)) {
        // console.log(`Processing Block ID: ${blockId}, Type: ${block.type}`);

        if (blockTypeMap[block.type]) {
            const blockHtml = blockTypeMap[block.type](block, blockId);  // Call the appropriate function
            appendBlockToDOM(blockHtml, block.dataPageId);
        } else {
            console.log(`Unknown block type: ${block.type}`);
        }
    }
}

export function convertToBlockFormat(originalJson) {
    // console.log('Original JSON:', originalJson);
    const containerBlocks = {};
    let blockIdCounter = 0;

    // Helper to generate a new block ID
    function generateBlockId() {
        return `block-${blockIdCounter++}`;
    }

    // Add the title block
    const titleBlockId = generateBlockId();
    containerBlocks[titleBlockId] = {
        type: 'title',
        dataPageId: 'block-container',
        title: originalJson.store_name,
        description: `${originalJson.store_description} ${originalJson.store_backstory} ${originalJson.store_reputation}`
    };

    // Add store properties block
    const propertiesBlockId = generateBlockId();
    containerBlocks[propertiesBlockId] = {
        type: 'store-properties',
        dataPageId: 'block-container',
        'store-size': originalJson.store_size,
        'store-location': originalJson.store_location.town,
        'store-district': originalJson.store_location.district,
        'store-street': originalJson.store_location.street,
        'store-type': originalJson.store_type,
        'store-hours': originalJson.store_hours,
        'store-services': originalJson.store_services.map(service => service.name),
        'store-specialties': originalJson.store_specialties.map(specialty => specialty.name),
        'store-rumors': originalJson.store_rumors,
        'store-reputation': originalJson.store_reputation
    };

    // Add image blocks (assuming you have multiple)
    if (originalJson.storefront_sd_prompt) {
        const storefrontImageBlockId = generateBlockId();
        containerBlocks[storefrontImageBlockId] = {
            type: 'image',
            dataPageId: 'block-container',
            sdprompt: originalJson.storefront_sd_prompt,
            imgUrl: ''
        };
    }

    // Add owner blocks
    originalJson.store_owners.forEach(owner => {
        const ownerBlockId = generateBlockId();
        containerBlocks[ownerBlockId] = {
            type: 'owner',
            dataPageId: 'block-container',
            name: owner.name,
            species: owner.species,
            class: owner.class,
            description: owner.description,
            personality: owner.personality,
            secrets: owner.secrets
        };
        if (owner.sd_prompt) {
            const storefrontImageBlockId = generateBlockId();
            containerBlocks[storefrontImageBlockId] = {
                type: 'image',
                dataPageId: 'block-container',
                sdprompt: owner.sd_prompt,
                imgUrl: ''
            };
        }
    });

    // Add employee blocks
    originalJson.store_employees.forEach(employee => {
        const employeeBlockId = generateBlockId();
        containerBlocks[employeeBlockId] = {
            type: 'employee',
            dataPageId: 'block-container',
            name: employee.name,
            role: employee.role,
            species: employee.species,
            description: employee.description,
            personality: employee.personality
        };
        if (employee.sd_prompt) {
            const storefrontImageBlockId = generateBlockId();
            containerBlocks[storefrontImageBlockId] = {
                type: 'image',
                dataPageId: 'block-container',
                sdprompt: employee.sd_prompt,
                imgUrl: ''
            };
        }
    });

    // Add quest blocks
    originalJson.store_quests.forEach(quest => {
        const questBlockId = generateBlockId();
        containerBlocks[questBlockId] = {
            type: 'quest',
            dataPageId: 'block-container',
            name: quest.name,
            description: quest.description,
            reward: quest.reward
        };
    });

    // Add customer blocks
    originalJson.store_customers.forEach(customer => {
        const customerBlockId = generateBlockId();
        containerBlocks[customerBlockId] = {
            type: 'customer',
            dataPageId: 'block-container',
            name: customer.name,
            description: customer.description,
            influence: customer.influence
        };
    });

    // Add security blocks
    originalJson.store_security.forEach(security => {
        const securityBlockId = generateBlockId();
        containerBlocks[securityBlockId] = {
            type: 'security',
            dataPageId: 'block-container',
            name: security.name,
            description: security.description,
            mechanics: security.mechanics
        };
    });

    // Add services blocks
    originalJson.store_services.forEach(service => {
        const serviceBlockId = generateBlockId();
        containerBlocks[serviceBlockId] = {
            type: 'services',
            dataPageId: 'block-container',
            name: service.name,
            description: service.description,
            price: service.price
        };
    });

    // Add specialties blocks
    originalJson.store_specialties.forEach(specialty => {
        const specialtyBlockId = generateBlockId();
        containerBlocks[specialtyBlockId] = {
            type: 'specialties',
            dataPageId: 'block-container',
            name: specialty.name,
            description: specialty.description,
            price: specialty.price
        };
    });

    // Add inventory block
    const inventoryBlockId = generateBlockId();
    containerBlocks[inventoryBlockId] = {
        type: 'inventory',
        dataPageId: 'block-container',
        core_inventory: originalJson.inventory.core_inventory,
        weapons: originalJson.inventory.weapons,
        armor: originalJson.inventory.armor,
        potions: originalJson.inventory.potions,
        scrolls: originalJson.inventory.scrolls,
        magical_items: originalJson.inventory.magical_items,
        mundane_items: originalJson.inventory.mundane_items,
        miscellaneous_items: originalJson.inventory.miscellaneous_items
    };
    // console.log('Container blocks:', containerBlocks);
    // console.log('Converted to block format:', containerBlocks);
    return { storeData: containerBlocks };

}