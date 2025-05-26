# DungeonMind - TTRPG Support Platform

DungeonMind is a platform designed to support tabletop role-playing game (TTRPG) players, game masters, and content creators. By leveraging a modular microservices architecture and powerful AI-driven tools, DungeonMind provides a seamless experience for creative TTRPG world-building and gameplay enhancement.

## Project Overview

DungeonMind is built with a **microservices architecture** that integrates several independent tools for TTRPG management. Key services include an interactive Rules-As-Guide (RAG) system, custom card generator, stat block creator, and store generator, along with a professional landing page to showcase these capabilities. This project highlights Alan Meigs' advanced skills in **React**, **FastAPI**, **NGINX**, **Docker**, and **generative AI technologies**.

## Key Features

- **Professional Landing Page**: A React-based landing page, served as a separate microservice, introduces the DungeonMind platform and demonstrates the tools available to users.
- **API Server**: Built with FastAPI, the API server handles backend logic and supports all the TTRPG tools with a RESTful architecture.
- **StoreGenerator Service**: A standalone service that enables users to create and manage in-game shops and stores for their campaigns, served as an independent microservice.
- **AI-Enhanced Tools**:
   - **Rules Lawyer**: An interactive Rules-As-Guide (RAG) system that provides in-context rule guidance for smoother gameplay.
   - **Card Generator**: Customizable TTRPG cards for characters, items, or spells, enhancing game immersion.
   - **Statblock Generator**: Automatic generation of stat blocks for characters and creatures, simplifying preparation for game masters.
- **NGINX and Cloudflare Configuration**: Efficient routing and redirection management to ensure secure, reliable, and fast access to all microservices.

## Project Goals

DungeonMind serves as a showcase for a modular, scalable TTRPG support platform, with the following goals:

1. **Demonstrate Advanced Development Skills**: Showcase Alan Meigs' ability to create a modern, microservices-based web application utilizing Docker, NGINX, FastAPI, and React.
2. **Enhance TTRPG Gameplay with AI and Automation**: Provide interactive, AI-driven tools that accelerate TTRPG world-building and make running campaigns smoother and more accessible.
3. **Provide a Robust, Scalable Demo Platform**: Create a flexible and scalable foundation to support further tool development and feature additions, with potential for future user expansion.

## Architecture

DungeonMind is structured as multiple microservices, each serving a distinct function:

- **Hostinger**: Domain and VPS.
- **Frontend Service**: Hosts the React-based landing page, showcasing the platform and handling user interactions.
- **DungeonMindAPI Server**: Manages backend logic, data processing, and serves as the central data API for all front-end interactions.
- **StoreGenerator Service**: A specialized service dedicated to generating and managing in-game shops and stores, isolated for independent scaling and functionality.
- **Reverse Proxy and Security**: NGINX handles routing and load balancing between services, while Cloudflare provides additional security, caching, and SSL/TLS support.
- **Cloudflare**: Providing caching, security, and DNS services.

## Deployment

DungeonMind uses Docker for containerization, with each service running in its own container. NGINX acts as a reverse proxy to route traffic to the appropriate service, while Cloudflare manages DNS, SSL, and caching. The architecture allows for smooth scaling of individual services as user demand increases.

## Future Plans

DungeonMind is an evolving project with plans to expand tool functionality, enhance generative AI integration, and support even more complex TTRPG systems. Planned features include enhanced user interfaces, expanded API endpoints, and a broader range of AI-driven TTRPG creation tools.

