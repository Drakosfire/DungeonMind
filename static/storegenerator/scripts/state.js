// state.js
let initialState = {
    originalContent: null,
    initialPositions: [],
    MAX_COLUMN_HEIGHT: 847,
    currentPage: null,
    jsonData: null,
};

export function getState() {
    return initialState;
}

export function updateState(key, value) {
    initialState[key] = value;
}

// Function to reset the state
export function resetState() {
    initialState = { ...initialState };
}