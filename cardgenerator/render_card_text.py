from PIL import ImageDraw, ImageFont

 # Function for managing longer bodies of text and breaking into a list of lines to be printed based on input arguments   
def split_text_into_lines(text, font, max_width, draw):
    blocks = text.split('\n')  
    lines = []
    for block in blocks:
        words = block.split()
        current_line = ''

        for word in words:
            # Check width with new word added
            test_line = f"{current_line} {word}".strip()
            test_width = draw.textlength(text = test_line, font=font)
            if test_width <= max_width:
                current_line = test_line
            else:
                #If the line with the new word exceeds the max width, start a new line
                lines.append(current_line)
                current_line = word
    # add the last line
        lines.append(current_line)
    return lines
# Function for calculating the height of the text at the current font setting
       

def adjust_font_size_lines_and_spacing(text, font_path, initial_font_size, max_width, area_height, image) :    
    font_size = initial_font_size
    optimal_font_size = font_size
    optimal_lines = []
    line_spacing_factor = 1.2 # multiple of font size that will get added between each line
    
    while font_size > 10: # Set minimum font size
        font = ImageFont.truetype(font_path, font_size)
        draw = ImageDraw.Draw(image)
        # Fitting text into box dimensions
        lines = split_text_into_lines(text, font, max_width, draw)
        # Calculate total height with dynamic line spacing
        single_line_height = draw.textbbox((0, 0), "Ay", font=font)[3] - draw.textbbox((0, 0), "Ay", font=font)[1]  # Height of 'Ay'
        line_spacing = int(single_line_height * line_spacing_factor) - single_line_height
        total_text_height = len(lines) * single_line_height + (len(lines) - 1) * line_spacing # Estimate total height of all lines by multiplying number of lines by font height plus number of lines -1 times line spacing

        if total_text_height <= area_height : 
            optimal_font_size = font_size
            optimal_lines = lines
            break # Exit loop font fits in contraints

        else: 
            font_size -= 1 # Reduce font by 1 to check if it fits             
        
    return optimal_font_size, optimal_lines, line_spacing     
# Function that takes in an image,text and properties for textfrom card_generator 
def render_text_with_dynamic_spacing(image, text, center_position, max_width, area_height,font_path, initial_font_size,description = None, quote = None):
    

    optimal_font_size, optimal_lines, line_spacing = adjust_font_size_lines_and_spacing(
        text, font_path, initial_font_size, max_width, area_height, image)
    # create an object to draw on 
    
    font = ImageFont.truetype(font_path, optimal_font_size)
    draw = ImageDraw.Draw(image)

     # Shadow settings
    shadow_offset = (1, 1)  # X and Y offset for shadow
    shadow_color = 'grey'  # Shadow color

    # Unsure about the following line, not sure if I want y_offset to be dynamic
    y_offset = center_position[1]         
    
    if description or quote : 
        for line in optimal_lines:
            line_width = draw.textlength(text = line, font=font)
            x = center_position[0] 
            # Draw Shadow first
            shadow_position = (x + shadow_offset[0], y_offset + shadow_offset[1])
            draw.text(shadow_position, line, font=font, fill=shadow_color)
            #Draw text
            draw.text((x, y_offset), line, font=font, fill = 'black', align = "left" )
            y_offset += optimal_font_size + line_spacing  # Move to next line
        return image  

    for line in optimal_lines:
        line_width = draw.textlength(text = line, font=font)
        x = center_position[0] - (line_width / 2)
        # Draw Shadow first
        shadow_position = (x + shadow_offset[0], y_offset + shadow_offset[1])
        draw.text(shadow_position, line, font=font, fill=shadow_color)
        #Draw text
        draw.text((x, y_offset), line, font=font, fill = 'black', align = "left" )
        y_offset += optimal_font_size + line_spacing  # Move to next line
    return image   

# Function to put the description objects together, this will be the complicated bit, I think iterate through keys excluding title, type and cost




