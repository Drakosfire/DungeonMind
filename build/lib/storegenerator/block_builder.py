# block_id is a global variable that is used to keep track of the current block id
block_id = 0

# This function takes in the user input and block_id and returns a list of blocks built with textareas 
def build_blocks(user_input, block_id):
    list_of_blocks = []
    title_block = build_title_block(user_input['store_name'], user_input['store_description'], user_input['store_backstory'], user_input['store_reputation'])
    block_id = block_id + 1
    list_of_blocks.append(title_block)
    store_image_block = build_image_block(user_input['storefront_sd_prompt'], block_id)
    block_id = block_id + 1
    list_of_blocks.append(store_image_block)
    store_properties_block = build_store_properties_block(store_type= user_input['store_type'],
                                                          store_size= user_input['store_size'],
                                                          store_hours= user_input['store_hours'],
                                                          store_location= user_input['store_location'],
                                                          store_owners= user_input['store_owners'],
                                                          store_employees= user_input['store_employees'],
                                                          store_services= user_input['store_services'],
                                                          store_specialties= user_input['store_specialties'],
                                                          store_reputation= user_input['store_reputation'],
                                                          store_rumors= user_input['store_rumors'],
                                                          block_id= block_id)
    block_id = block_id + 1
    list_of_blocks.append(store_properties_block)

    owner_id = 1
    # Employee and owner could be combined into a single function with a parameter for the type of block
    # Iterate over owners and generate owner image and details block
    owner_title = "Owner"
    if len(user_input['store_owners']) > 1:
        owner_title = "Owners"
    owner_title_block = f"""<h2 id="owner">{owner_title}</h2>"""    

    for owner in user_input['store_owners']:
        owner_image_block = build_image_block(owner['sd_prompt'], block_id)
        block_id = block_id + 1
        list_of_blocks.append(owner_image_block)
        owner_block = build_owner_block(owner,owner_id, owner_title_block, block_id)
        block_id = block_id + 1
        list_of_blocks.append(owner_block)
        owner_id += 1
    employee_id = 1
    
    # Iterate over employees and generate employee image and details block
    employee_title = "Employee"
    if len(user_input['store_employees']) > 1:
        employee_title = "Employees"
    employee_title_block = f"""<h2 id="employee">{employee_title}</h2>"""
    for employee in user_input['store_employees']:

        employee_image_block = build_image_block(employee['sd_prompt'], block_id)
        block_id = block_id + 1
        list_of_blocks.append(employee_image_block)
        employee_block = build_employee_block(employee, employee_id, employee_title_block, block_id)
        block_id = block_id + 1
        list_of_blocks.append(employee_block)
        employee_id += 1
    
    customer_id = 1
    for customer in user_input['store_customers']:
        customers_block = build_section_entry_block('Customers',customer, customer_id, block_id)
        block_id = block_id + 1
        customer_id += 1
        list_of_blocks.append(customers_block)

    quest_id = 1
    for quest in user_input['store_quests']:
        quests_block = build_section_entry_block('Store Quests', quest, quest_id, block_id)
        block_id = block_id + 1
        quest_id += 1
        list_of_blocks.append(quests_block)
    
    services_id = 1
    for service in user_input['store_services']:
        services_block = build_section_entry_block('Services', service, services_id, block_id)
        block_id = block_id + 1
        services_id += 1
        list_of_blocks.append(services_block)

    specialties_id = 1
    for specialty in user_input['store_specialties']:
        specialty_block = build_section_entry_block('Specialties', specialty, specialties_id, block_id)
        block_id = block_id + 1
        specialties_id += 1
        list_of_blocks.append(specialty_block)
    
    security_id = 1
    for security in user_input['store_security']:
        security_block = build_section_entry_block('Security', security, security_id, block_id)
        block_id = block_id + 1
        security_id += 1
        list_of_blocks.append(security_block)

    inventory_block = build_inventory_block(user_input['inventory'], block_id)
    block_id = block_id + 1
    list_of_blocks.append(inventory_block)

    return list_of_blocks

# Take in a specific item type and item, and return the html for that item
def process_into_html(item_type,item, block_id):
     item_html = f"""<tr>
                <td align="left"><strong>{item_type}</strong></td>
                <td align="right"><textarea class="string-action-description-textarea" id="{item_type}-{block_id}"
                hx-post="/update-stats" hx-trigger="change" hx-target="#user-store-owners-{block_id}t" hx-swap="outerHTML"
                title="">{item}</textarea></td>
            </tr>"""
     return item_html

# Take in a specific iterable type and iterable, and return the html for that iterable
def process_iterable_into_html(iterable_type, iterable, block_id):
    iterable_html = f""""""
    for item in iterable:
        item_html = f"""<tr>
                <td align="left"><strong>{iterable_type}</strong></td>
                <td align="right"><textarea class="string-action-description-textarea" id="user-store-owners-{block_id}"
                hx-post="/update-stats" hx-trigger="change" hx-target="#user-store-owners-{block_id}t" hx-swap="outerHTML"
                title="">{item['name']}</textarea></td>
            </tr>"""
        iterable_html += item_html
    return iterable_html

# Take in a list of rumors and return the html for that list of rumors
def process_rumors_into_html(rumors, block_id):
        rumors_html = f""""""
        for rumor in rumors:
            rumor_html = f"""<tr>
                    <td align="left"><strong>Store Rumors</strong></td>
                    <td align="right"><textarea class="string-action-description-textarea" id="user-store-rumors-{block_id}"
                  hx-post="/update-stats" hx-trigger="change" hx-target="#user-store-rumors-{block_id}t" hx-swap="outerHTML"
                  title="Rumors">{rumor}</textarea></td>
                </tr>"""
            rumors_html += rumor_html
        return rumors_html

# Take in a list of secrets and return the html for that list of secrets    
def process_secrets_into_html(secrets, block_id):
        secrets_html = f""""""
        for secret in secrets:
            secret_html = f"""<tr>
                    <td align="left"><strong>Secrets</strong></td>
                    <td align="right"><textarea class="string-action-description-textarea" id="user-store-rumors-{block_id}"
                  hx-post="/update-stats" hx-trigger="change" hx-target="#user-store-rumors-{block_id}t" hx-swap="outerHTML"
                  title="Store Size">{secret}</textarea></td>
                </tr>"""
            secrets_html += secret_html
        return secrets_html

# Block for title, description, backstory, and reputation
def build_title_block(title,description,backstory,reputation):
     title_block_html = f"""<div class="block-item" data-block-id = {block_id}><h1>
     <textarea class="title-textarea" id="user-store-title" hx-post="/update-stats" hx-trigger="change" hx-target="#user-store-name" hx-swap="outerHTML" title="Name of store">{title}</textarea></h1>
     <div contenteditable="true" class="description-textarea" id="user-store-description"
         hx-post="/update-stats" hx-trigger="change"
         hx-target="#user-monster-description" hx-swap="outerHTML"
         title="Any amount or style of description">
        <p>{f"{description} {backstory} {reputation}"}</p>
    </div> """
     
     return title_block_html
# Block for image generation
def build_image_block(sd_prompt, block_id):
    image_block_html = f"""
    <div class="block-item" data-block-id="{block_id}">
        <textarea class="image-textarea" id="sdprompt-{block_id}"
                  hx-post="/update-stats" hx-trigger="change" hx-target="#sd-prompt-{block_id}" hx-swap="outerHTML"
                  title="Storefront image description">{sd_prompt}</textarea>
        <button class="generate-image-button" data-block-id="{block_id}" >
            <img src="/static/storegenerator/images/StoreGeneratorGenerateButton.png" alt="Generate Image">
        </button>
        <img id="generated-image-{block_id}" alt="" style="display: none; cursor: pointer;">
    </div>
    """

    return image_block_html

# Block for store properties
def build_store_properties_block(store_type,
                                 store_size,
                                 store_hours,
                                 store_location,
                                 store_owners,
                                 store_employees,
                                 store_services,
                                 store_specialties,
                                 store_reputation,
                                 store_rumors,
                                 block_id):
    
    # This could be the iterable block function with additional flexibility
    store_properties_base_html = f"""
    <div class="block-item" data-block-id="{block_id}">
    <div class="block classTable frame decoration">
        <table>
            <thead>
                <tr>
                    <th align="left"></th>
                    <th align="center"></th>
                    <th align="center"></th>
                </tr>
            </thead>
            <tbody>
                <tr> 
                    <td align="left"><strong>Size</strong></td>
                    <td align="right"><textarea class="string-action-description-textarea" id="user-store-size-{block_id}"
                  hx-post="/update-stats" hx-trigger="change" hx-target="#user-store-size-{block_id}t" hx-swap="outerHTML"
                  title="Store Size">{store_size}</textarea></td>
                </tr>
                <tr>
                    <td align="left"><strong>Town</strong></td>
                    <td align="right"><textarea class="string-action-description-textarea" id="user-store-town-{block_id}"
                  hx-post="/update-stats" hx-trigger="change" hx-target="#user-store-town-{block_id}t" hx-swap="outerHTML"
                  title="Store Size">{store_location['town']}</textarea></td>
                </tr>
                <tr>
                    <td align="left"><strong>District</strong></td>
                    <td align="right"><textarea class="string-action-description-textarea" id="user-store-district-{block_id}"
                  hx-post="/update-stats" hx-trigger="change" hx-target="#user-store-district-{block_id}t" hx-swap="outerHTML"
                  title="Store Size">{store_location['district']}</textarea></</td>
                </tr>
                <tr>
                    <td align="left"><strong>Street</strong></td>
                    <td align="right"><textarea class="string-action-description-textarea" id="user-store-street-{block_id}"
                  hx-post="/update-stats" hx-trigger="change" hx-target="#user-store-street-{block_id}t" hx-swap="outerHTML"
                  title="Store Size">{store_location['street']}</textarea></</td>
                </tr>
                <tr>
                    <td align="left"><strong>Type</strong></td>
                    <td align="right"><textarea class="string-action-description-textarea" id="user-store-type-{block_id}"
                  hx-post="/update-stats" hx-trigger="change" hx-target="#user-store-type-{block_id}t" hx-swap="outerHTML"
                  title="Store Size">{store_type}</textarea></</td>
                </tr>
                <tr>
                 <tr>
                    <td align="left"><strong>Store Hours</strong></td>
                    <td align="right"><textarea class="string-action-description-textarea" id="user-store-hours-{block_id}"
                  hx-post="/update-stats" hx-trigger="change" hx-target="#user-store-hours-{block_id}t" hx-swap="outerHTML"
                  title="Store Size">{store_hours}</textarea></td>
                </tr> """
    store_owners = []
    store_employees = []
    owners_html = process_iterable_into_html('Store Owners', store_owners, block_id)
    employees_html = process_iterable_into_html('Store Employees', store_employees, block_id)
    store_specialties_html = process_iterable_into_html('Store Specialties', store_specialties, block_id)
    store_services_html = process_iterable_into_html('Store Services', store_services, block_id)
    store_rumors_html = process_rumors_into_html(store_rumors, block_id)
    store_iterables_html = f"""
                {owners_html}
                {employees_html}
                {store_services_html}
                {store_specialties_html}
                {store_rumors_html}
                """
    store_end_html = f"""
                <tr>
                    <td align="left"><strong>Store Reputation</strong></td>
                    <td align="right"><textarea class="string-action-description-textarea" id="user-store-reputation-{block_id}"
                  hx-post="/update-stats" hx-trigger="change" hx-target="#user-store-reputation-{block_id}t" hx-swap="outerHTML"
                  title="Store Size">{store_reputation}</textarea></td>
                </tr>
            </tbody>
        </table>
    </div>
    </div>
    """
    store_properties_block_html = f"""{store_properties_base_html}
                {store_iterables_html}
                {store_end_html}"""
    return store_properties_block_html

# Block of owner table
def build_owner_block(owner, owner_id, owner_title_block, block_id):
    # Owner block with values : Name, Race, Class, Description, Personality, Secrets, sd-prompt
    
    # Process owner values into html
    owner_name_html = process_into_html('Owner', owner['name'], block_id)
    owner_race_html = process_into_html('Species', owner['species'], block_id)
    owner_class_html = process_into_html('Class', owner['class'], block_id)
    owner_description_html = process_into_html('Description', owner['description'], block_id)
    owner_personality_html = process_into_html('Personality', owner['personality'], block_id)
    owner_secrets_html = process_secrets_into_html(owner['secrets'], block_id)
    # Build owner block html
    # If owner_id is 1, add owner_title_block to owner_block_html
    
    owner_block_html = f""""""
    owner_block_html += f"""<div class="block-item" data-block-id="{block_id}">"""
    if owner_id == 1:
        owner_block_html+= owner_title_block
    owner_block_html += f"""<h3 id="owner_{owner_id}"><textarea class="subtitle-textarea" id="user-store-rumors-{block_id}"
                  hx-post="/update-stats" hx-trigger="change" hx-target="#user-store-rumors-{block_id}t" hx-swap="outerHTML"
                  title="Owner Name">{owner['name']}</textarea></h3>"""
    owner_block_html += f"""<table>
                                <thead>
                                    <tr>
                                        <th align="center"></th>
                                        <th align="center"></th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {owner_name_html}
                                    {owner_race_html}
                                    {owner_class_html}
                                    {owner_description_html}
                                    {owner_personality_html}
                                    {owner_secrets_html}
                                </tbody>
                            </table>
                            </div>
    """
    return owner_block_html

# Block of employee table
def build_employee_block(employee, employee_id, employee_title_block, block_id):
    # Employee block with name, role, species, description, personality, sd-prompt
    # Process employee values into html
    employee_name_html = process_into_html('Employee', employee['name'], block_id)
    employee_role_html = process_into_html('Role', employee['role'], block_id)
    employee_species_html = process_into_html('Species', employee['species'], block_id)
    employee_description_html = process_into_html('Description', employee['description'], block_id)
    employee_personality_html = process_into_html('Personality', employee['personality'], block_id)
    # Build employee block html

    employee_block_html = f""""""
    employee_block_html += f"""<div class="block-item" data-block-id="{block_id}">"""
    if employee_id == 1:
        employee_block_html += employee_title_block
    employee_block_html += f"""<h3 id="owner_{employee_id}"><textarea class="subtitle-textarea" id="user-store-rumors-{block_id}"
                                    hx-post="/update-stats" hx-trigger="change" hx-target="#user-store-rumors-{block_id}t" hx-swap="outerHTML"
                                    title="Owner Name">{employee['name']}</textarea>
                                </h3>
                                <table>
                                    <thead>
                                        <tr>
                                            <th align="center"></th>
                                            <th align="center"></th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {employee_name_html}
                                        {employee_role_html}
                                        {employee_species_html}
                                        {employee_description_html}
                                        {employee_personality_html}
                                    </tbody>
                                </table>
                                </div>
    """
    return employee_block_html

# Section to take in a section name, entry, entry_id, and block_id and return the html for that section
def build_section_entry_block(section, entry, entry_id, block_id):
    section_block_html = f""""""
    section_block_html += f"""<div class="block-item" data-block-id="{block_id}">"""
    if entry_id == 1:
        section_block_html += f"""<h1 id="store-quests">{section}</h1> """
    entry_features_list = list(entry.keys())
    for feature in entry_features_list:
        if feature == 'name':
            section_block_html += f"""<h3 id="quest={entry_id}">
                        <textarea class="subtitle-textarea" id="user-store-{section}-{block_id}"
                        hx-post="/update-stats" hx-trigger="change" hx-target="#user-store-rumors-{block_id}t" hx-swap="outerHTML"
                        title={section}>{entry['name']}</textarea>
                        </h3>"""
        else:
            feature_name = feature[0].upper() + feature[1:]
            section_block_html += f"""<p>
                        <textarea class="string-action-description-textarea" id="user-store-{section}-{block_id}"
                        hx-post="/update-stats" hx-trigger="change" hx-target="#user-store-{section}-{block_id}t" hx-swap="outerHTML"
                        title={section}>{feature_name}: {entry[feature]}</textarea>
                        </p>"""
    
    return section_block_html

def build_inventory_block(inventory, block_id):
    inventory_block_html = f""""""
    inventory_block_html += f"""<div class="block-item" data-block-id="{block_id}">"""
    inventory_block_html += f"""<div class="block classTable frame decoration">
                                    <h5 id="inventory">Inventory</h5>
                                        <table>
                                            <thead>
                                                <tr>
                                                    <th align="center">Name</th>
                                                    <th align="center">Type</th>
                                                    <th align="left">Cost</th>
                                                    <th align="center">Properties</th>
                                                </tr>
                                            </thead>
                                            <tbody>"""
    # Create a list of the keys in the inventory, each key is the type of items
    list_of_type = list(inventory.keys())
    # Iterate through keys and check if the value is greater than an empty list
    for type in list_of_type:
        inventory_type = inventory[type]
        if len(inventory_type) > 0 :
            # iterate through items in inventory type list, each item is a dictionary with prescribed values.
            # Need to check for list in properties.
            for item in inventory_type:
                item['properties'] = ', '.join(item['properties'])
                item_block_html = f"""<tr>
                                        <td align="center"><textarea class="string-action-description-textarea" id="user-store-rumors-{block_id}"
                        hx-post="/update-stats" hx-trigger="change" hx-target="#user-store-rumors-{block_id}t" hx-swap="outerHTML"
                        title={type}>{item['name']}</textarea></td>
                                        <td align="center"><textarea class="string-action-description-textarea" id="user-store-rumors-{block_id}"
                        hx-post="/update-stats" hx-trigger="change" hx-target="#user-store-rumors-{block_id}t" hx-swap="outerHTML"
                        title={type}>{item['type']}</textarea></td>
                                        <td align="center"><textarea class="string-action-description-textarea" id="user-store-rumors-{block_id}"
                        hx-post="/update-stats" hx-trigger="change" hx-target="#user-store-rumors-{block_id}t" hx-swap="outerHTML"
                        title={type}>{item['cost']}</textarea></td>
                                        <td align="center"><textarea class="string-action-description-textarea" id="user-store-rumors-{block_id}"
                        hx-post="/update-stats" hx-trigger="change" hx-target="#user-store-rumors-{block_id}t" hx-swap="outerHTML"
                        title={type}>{item['properties']}</textarea></td>
                                    </tr>"""
                
                inventory_block_html += item_block_html
    inventory_block_html += f"""</tbody>
                            </table>
                            </div> 
                        </div>"""
    return inventory_block_html
