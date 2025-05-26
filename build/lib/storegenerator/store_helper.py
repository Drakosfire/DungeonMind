import ast
import gc
from openai import OpenAI

client = OpenAI()

def load_llm(user_input, prompt_instructions):
    prompt = f"{user_input}"
    print(prompt)
    response = client.chat.completions.create(            
                    model="gpt-4o-2024-08-06",
                    messages=[
                        {
                        "role": "user",
                        "content": f"{prompt_instructions}  {prompt}"
                        }
                    ],
                    temperature=1,
                    max_tokens=3000,
                    top_p=1,
                    frequency_penalty=0,
                    presence_penalty=0
                    )
    print(f"Model : {response.model}")
    return response.choices[0].message.content
# Call the LLM and store its output
def call_llm_and_cleanup(user_input, inventory = False): 
    
    prompt_instructions = f"{initial_prompt_instructions} {store_description}"
    
    llm_output = load_llm(user_input, prompt_instructions)
    llm_output = "".join(llm_output)
    print(llm_output)
    llm_output = convert_to_dict(llm_output)
    gc.collect()
    # llm_output is still available for use here
    return llm_output
  
def convert_to_dict(string):
    # Check if the input is already a dictionary
    if isinstance(string, dict):
        print("Input is already a dictionary.")
        return string

    # Function to try parsing the string to a dictionary
    def try_parse(s):
        try:
            result = ast.literal_eval(s)
            if isinstance(result, dict):
                print("Item dictionary is valid")
                return result
        except SyntaxError as e:
          error_message = str(e)
          print("Syntax Error:", error_message)
          # Check if the error message indicates an unclosed '{'
          if "'{' was never closed" in error_message:
              return try_parse(s + '}')  # Attempt to fix by adding a closing '}'
        except ValueError as e:
            print("Value Error:", e)
        return None 

    # First, try parsing the original string
    result = try_parse(string)
    if result is not None:
        return result

    # Check if braces are missing
    if not string.startswith('{'):
        string = '{' + string
    if not string.endswith('}'):
        string = string + '}'

    # Try parsing again with added braces
    return try_parse(string) or "Dictionary not valid"
        
  

# Instructions past 4 are not time tested and may need to be removed.
### System prompt : 
initial_prompt_instructions = """ **Purpose**: ONLY Generate a structured json following the provided format. The job is to generate a store with character, style, detail, and a healthy splash of fun, fantasy, and weird. You do not need to stick strictly to the rules and mechanics of the game, if it fits the style and flavor of the user input, get weird, scary, or silly with the details. You will also be writing interesting flavor text and description of the location and it's atmopshere, and a brief one sentence image generation prompts. Us a wide range of words, you have certain words you use too often, avoid them ex : "whimsical", "unwavering".

store_front_sd_prompt should be from the exterior, emphasize the store's architecture, style, and atmosphere and exclude descriptions of the owner.

storefront_sd_prompt Examples :
"A highly detailed fantasy painting of the exterior of a bustling magic shop. The shop is adorned with glowing runes, enchanted crystals, and mystical artifacts. The shop sign reads "Arcane Emporium" in elegant script. The street is filled with magical creatures, floating lanterns, and colorful stalls. "

"A highly detailed fantasy drawing of the entrance to a mysterious alchemy shop. The shop is hidden down a narrow alley, with a flickering lantern above the door. The shop sign reads "Elixir Emporium" in faded letters. The alley is filled with shadows, strange smells, and the distant sound of bubbling potions. "

"A highly detailed fantasy photo of the front of a grand weapon shop. The shop is decorated with suits of armor, hanging banners, and a large sword embedded in the stone facade. The shop sign reads "Ironclad Armory" in bold letters. The street is filled with armored guards, clashing swords, and the sound of ringing anvils. "

Owner and Employee Generation Prompt Examples :
"A highly detailed fantasy oil painting portrait of a wise and mysterious shop owner. The owner is an elderly elf with silver hair, a long beard, and piercing blue eyes. They wear flowing robes, a jeweled amulet, and a crown of thorns. The owner is surrounded by magical artifacts, ancient tomes, and glowing crystals."

"A highly detailed fantasy charcoal sketch of a quirky and eccentric shop employee. The employee is a young gnome with wild hair, mismatched eyes, and a mischievous grin. They wear patched clothes, a bandolier of potions, and a pet dragon perched on their shoulder. The employee is surrounded by alchemical ingredients, bubbling cauldrons, and floating spellbooks."

"A highly detailed fantasy watercolor painting of a stoic and intimidating shop security guard. The guard is a massive half-orc with a shaved head, a scarred face, and a stern expression. They wear heavy armor, a massive sword, and a shield emblazoned with a roaring lion. The guard is surrounded by chained beasts, locked chests, and glowing runes."

1. Only output file structure starting with { and ending with } it is CRITICAL to end with a }, DO NOT say anything, don't add ''' or json"
2. DO NOT use null, use "". 
3. All keys and values MUST be enclosed in double quotes. ""
4. Services and specialties should have name, description, and prices. 
5. sd_prompts should specify race or species
6. quests MUST be detailed, and interesting, preferably unexpected, delightful and memorable. 
7. The reward for the quest MUST be specific and detailed!

Inventory Instructions:
1. Core Inventory should include at least five items.
2.Many categories of items wont make sense for most stores. IE Butchers Shops do not need magic items and potions. They might have them, but they would be very specific and probably not for sale at a reasonable price. Similarly a weapon shop does not need to sell basic traveling goods. 
3.. ALL items have "properties :" 
"""

store_description = {
    "store_name": "",
    "store_description": "",
    "store_reputation": "",
    "store_backstory": "",
    "storefront_sd_prompt": "",    
    "store_type": "",
    "store_size": "", 
    "store_hours": "", 
    "store_location": {
        "town": "",
        "district": "",
        "street": ""
    }, 
    "store_owners": [
        {
            "name": "",
            "species": "",
            "class": "",
            "description": "",
            "personality": "",
            "secrets": [],
            "sd_prompt":""
        }
    ],
    "store_employees": [
        {
            "name": "",
            "role": "",
            "species": "",
            "description": "",
            "personality": "",
            "sd_prompt":""
        }
    ],
    
    "store_quests": [
        {
            "name": "",
            "description": "",
            "reward": ""
        }
    ],
    
    "store_customers": [
        {
            "name": "",
            "description": "",
            "influence": ""
        }
    ],
    "store_rumors": [],
    "store_security": [
        {
            "name": "",
            "description": "",
            "mechanics": ""
        }
    ],
    
    "store_services": [
        {
            "name": "",
            "description": "",
            "price": ""
        }
    ],
    "store_specialties": [
        {
            "name": "",
            "description": "",
            "price": ""
        }
    ],
    
    "inventory": {
        "core_inventory":[
            {
                "name": "",
                "type": "",
                "cost": "",
                "properties": []
            }
        ],
        "weapons": [
            {
                "name": "",
                "type": "",
                "cost": "",
                "properties": []
            }
        ],
        "armor": [
            {
                "name": "",
                "type": "",
                "cost": "",
                "properties": []
            }
        ],
        "potions": [
            {
                "name": "",
                "type": "",
                "cost": "",
                "properties": []
            }
        ],
        "scrolls": [
            {
                "name": "",
                "type": "",
                "cost": "",
                "properties": []
            }
        ],
        "magical_items": [
            {
                "name": "",
                "type": "",
                "cost": "",
                "properties": []
            }
        ],
        "mundane_items": [
            {
                "name": "",
                "type": "",
                "cost": "",
                "properties": []
            }
        ],
        "miscellaneous_items": [
            {
                "name": "",
                "type": "",
                "cost": "",
                "properties": []
            }
        ]
    }
}

inventory_prompt_instructions = """


1. Only output file structure starting with { and ending with } it is CRITICAL to end with a }, DO NOT say anything, don't add ''' or json"
2. DO NOT use null, use "". 
3. All keys and values MUST be enclosed in double quotes. "" 
4. Many categories of items wont make sense for most stores. IE Butchers Shops do not need magic items and potions. They might have them, but they would be very specific and probably not for sale at a reasonable price. Similarly a weapon shop does not need to sell basic traveling goods. 
5. ALL items have "properties :" 
"""

inventory_description = {
    "inventory": {
        "core_inventory":[
            {
                "name": "",
                "type": "",
                "cost": "",
                "properties": []
            }
        ],
        "weapons": [
            {
                "name": "",
                "type": "",
                "cost": "",
                "properties": []
            }
        ],
        "armor": [
            {
                "name": "",
                "type": "",
                "cost": "",
                "properties": []
            }
        ],
        "potions": [
            {
                "name": "",
                "type": "",
                "cost": "",
                "properties": []
            }
        ],
        "scrolls": [
            {
                "name": "",
                "type": "",
                "cost": "",
                "properties": []
            }
        ],
        "magical_items": [
            {
                "name": "",
                "type": "",
                "cost": "",
                "properties": []
            }
        ],
        "mundane_items": [
            {
                "name": "",
                "type": "",
                "cost": "",
                "properties": []
            }
        ],
        "miscellaneous_items": [
            {
                "name": "",
                "type": "",
                "cost": "",
                "properties": []
            }
        ]
    }
}

