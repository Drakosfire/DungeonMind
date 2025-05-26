
# Project Plan for Pixel Art Landing Page (SNES/Genesis Boot-Up Style)

### Objective
Create a visually impressive landing page with a SNES/Genesis boot-up style using pixel art, React, and TypeScript. The landing page will feature a layered scene with moving clouds, a verdant hill, and an interactive chest that reveals a mimic on click, followed by a zoom-in transition to a new landing page.

---

## Roadmap

### Step 1: Set Up React + TypeScript Project
1. **Create a new React project with TypeScript**:
   - Use the following command to set up a React project with TypeScript:
     ```bash
     npx create-react-app dungeon-mind --template typescript
     ```

2. **Structure the project**:
   - Move the static HTML landing page (`index.html`) into React components.

---

### Step 2: Create the Landing Page Layout in React
1. **Structure the scene using JSX**:
   - Create components for each element of the scene (clouds, hill, chest).
   - Use JSX to structure the landing page.

2. **Example Structure**:
   ```tsx
   const LandingPage: React.FC = () => {
     return (
       <div className="scene">
         <div className="layer clouds"></div>
         <div className="layer hill"></div>
         <div className="layer chest"></div>
       </div>
     );
   };
   export default LandingPage;
   ```

---

### Step 3: Animate Clouds & Hill
1. **Cloud animation**:
   - Use CSS animations to move clouds across the screen.

2. **Example CSS**:
   ```css
   .clouds {
     background-image: url('/path/to/clouds.png');
     animation: moveClouds 30s linear infinite;
   }

   @keyframes moveClouds {
     from { transform: translateX(0); }
     to { transform: translateX(-100%); }
   }
   ```

---

### Step 4: Interactive Chest (Mimic Reveal)
1. **Add a clickable chest**:
   - Use React's `useState` to toggle between the chest and the mimic.

2. **Example React code**:
   ```tsx
   const LandingPage: React.FC = () => {
     const [isMimic, setIsMimic] = useState(false);

     const handleClick = () => {
       setIsMimic(true);
     };

     return (
       <div className="scene">
         <div className="layer clouds"></div>
         <div className="layer hill"></div>
         <div className="layer chest" onClick={handleClick}>
           {isMimic ? <Mimic /> : <Chest />}
         </div>
       </div>
     );
   };
   ```

---

### Step 5: Zoom In and Transition to Landing Page
1. **Zoom effect on mimic reveal**:
   - Use CSS transformations to zoom in on the scene when the mimic appears.

2. **Example CSS**:
   ```css
   .zoom-in {
     animation: zoomEffect 1s forwards;
   }

   @keyframes zoomEffect {
     from { transform: scale(1); }
     to { transform: scale(3); }
   }
   ```

3. **Transition to the landing page**:
   - After the zoom, fade to the actual landing page with main content.

---

### Pixel Art Resources
- **Pixel Art Tools**: Free pixel art tools like Piskel or Aseprite.
- **Assets**: Find pixel art assets on sites like OpenGameArt or Kenney.

---

### Next Steps:
1. Set up the React + TypeScript project.
2. Begin with the landing page structure, and we’ll implement the animations and interactivity step-by-step.
