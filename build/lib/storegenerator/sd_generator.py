import fal_client
def preview_and_generate_image(sd_prompt):   
    handler = fal_client.submit(
        "fal-ai/flux/dev",
        arguments={
            "prompt": f"{sd_prompt}",
            "num_inference_steps": 28,
            "guidance_scale": 3.5,

        },
    )

    result = handler.get()
    return result['images'][0]['url']
