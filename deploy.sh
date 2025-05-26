#!/bin/bash

set -e  # Exit immediately if a command exits with a non-zero status.

# Stop the Docker container
echo "Stopping Docker container 'dungeonmind-container'..."
docker stop dungeonmind-container || true  # Don't fail if container doesn't exist

# Remove the Docker container
echo "Removing Docker container 'dungeonmind-container'..."
docker rm dungeonmind-container || true  # Don't fail if container doesn't exist

# Remove the Docker image
echo "Removing Docker image 'dungeonmind-image'..."
docker rmi dungeonmind-image || true  # Don't fail if image doesn't exist

# Navigate to /var/www/DungeonMind directory
echo "Navigating to /var/www/DungeonMind directory..."
cd /var/www/DungeonMind

# Update the main repository
echo "Updating the DungeonMind repository..."
git fetch origin
git reset --hard origin/main  # Replace 'main' with your branch name if different

# Update the submodule
echo "Updating the storegenerator submodule..."
git submodule update --init --recursive
git submodule update --remote --merge

# Extract images using the extractimages.sh script
echo "Extracting images..."
./extractimages.sh

# Build the Docker image
echo "Building Docker image 'dungeonmind-image'..."
docker build --build-arg ENVIRONMENT=production -t dungeonmind-image .

# Run the Docker container with the specified environment file and port mapping
echo "Running Docker container 'dungeonmind-container'..."
sudo docker run -v /var/www/DungeonMind/saved_data:/home/user/app/saved_data --env-file .env -d -p 7860:7860 --name dungeonmind-container dungeonmind-image

echo "Script execution completed."
