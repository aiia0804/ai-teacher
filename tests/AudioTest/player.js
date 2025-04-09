// player.js

// Ensure only initialize once
if (!window.audioPlayerGlobalState) {
    console.log("Initializing player.js state and listeners...");

    window.audioPlayerGlobalState = {
        playerElement: null,
        statusElement: null,
        startButtonElement: null,
        queueListElement: null,
        // commElement: null, // No longer needed for polling
        audioQueue: [],
        isPlaying: false,
        currentIndex: -1,
        isInitialized: false, // Mark if DOM is ready
        // commCheckInterval: null // No longer needed
    };

    // --- Player Core Logic (updateQueueDisplay, playNextInQueue remain largely the same) ---
    function updateQueueDisplay() {
        const state = window.audioPlayerGlobalState;
        if (!state.isInitialized) return;
        console.log("player.js: updateQueueDisplay. Queue:", JSON.stringify(state.audioQueue.map(i => i.name))); // Log names for clarity

        state.queueListElement.innerHTML = ''; // Clear list
        if (state.audioQueue.length === 0) {
            const li = document.createElement('li');
            li.id = "empty-queue-message"; // Keep ID for consistency if needed elsewhere
            li.textContent = 'Queue is empty';
            state.queueListElement.appendChild(li);
            state.startButtonElement.disabled = true;
            state.startButtonElement.textContent = "▶️ Start Queue";
        } else {
            state.audioQueue.forEach((item, index) => {
                const li = document.createElement('li');
                li.textContent = `(${index + 1}) ${item.name}`;
                li.style.padding = "3px 0";
                li.style.borderBottom = "1px dashed #eee";
                li.style.color = (index === state.currentIndex) ? '#007bff' : '#333';
                li.style.fontWeight = (index === state.currentIndex) ? 'bold' : 'normal';
                state.queueListElement.appendChild(li);
            });
            // Enable start button if not playing
            if (!state.isPlaying) {
                 state.startButtonElement.disabled = false;
                 state.startButtonElement.textContent = "▶️ Start Queue";
            }
        }
         // Ensure list scrolls to bottom if overflowing
        state.queueListElement.scrollTop = state.queueListElement.scrollHeight;
    }

    function playNextInQueue() {
        const state = window.audioPlayerGlobalState;
        if (!state.isInitialized) {
            console.warn("player.js: playNextInQueue called before initialization.");
            return;
        }
        console.log("player.js: playNextInQueue. Queue length:", state.audioQueue.length, "isPlaying:", state.isPlaying);

        // Check if already playing *or* if the queue became empty before we could play
        if (state.isPlaying || state.audioQueue.length === 0) {
             if (state.audioQueue.length === 0 && !state.isPlaying) {
                state.statusElement.textContent = 'Queue empty, cannot play.';
                state.currentIndex = -1;
                updateQueueDisplay(); // Will disable button
             } else if (state.isPlaying) {
                 console.log("player.js: Already playing, skipping playNextInQueue call.");
             }
            return;
        }

        state.isPlaying = true;
        state.startButtonElement.disabled = true; // Disable while attempting to play
        state.startButtonElement.textContent = "🔄 Playing...";

        // Get the *next* item (always the first in the queue)
        // We don't remove it until it *finishes* playing in the 'ended' event
        const nextAudio = state.audioQueue[0];
        state.currentIndex = 0; // Index relative to the *current* queue view

        state.statusElement.textContent = `Preparing: ${nextAudio.name}`;
        console.log(`player.js: Preparing index 0: ${nextAudio.name}`);
        updateQueueDisplay(); // Highlight the item

        try {
            // Ensure player is reset if needed (e.g., previous error state)
            state.playerElement.pause();
            state.playerElement.currentTime = 0;
            state.playerElement.src = nextAudio.src; // Set the source
            console.log("player.js: Set source. Calling player.play()...");

            // Use promise to handle async play() and potential errors
            const playPromise = state.playerElement.play();

            if (playPromise !== undefined) {
                playPromise.then(_ => {
                    console.log(`player.js: Playback started: ${nextAudio.name}`);
                    state.statusElement.textContent = `Playing: ${nextAudio.name}`;
                    // Button remains disabled while playing
                }).catch(error => {
                    console.error(`player.js: player.play() FAILED for ${nextAudio.name}:`, error);
                    state.statusElement.textContent = `Play Error: ${error.message.substring(0, 100)}`; // Limit error message length
                    state.isPlaying = false;
                    state.currentIndex = -1; // Reset index
                    // Error handling: Optionally remove the faulty item or just allow user to try again/skip
                    // state.audioQueue.shift(); // Example: Remove faulty item
                    updateQueueDisplay(); // Update UI (might re-enable button if queue still has items)
                    // Try to play the *next* item if there was an error and we removed the faulty one
                    // if (state.audioQueue.length > 0) setTimeout(playNextInQueue, 100);
                });
            } else {
                 // Fallback for browsers that don't return a promise (rare)
                 console.log(`player.js: Playback initiated (no promise): ${nextAudio.name}`);
                 state.statusElement.textContent = `Playing: ${nextAudio.name}`;
            }
        } catch (err) {
            console.error("player.js: Error setting src or calling play:", err);
            state.statusElement.textContent = `Player Error: ${err.message.substring(0,100)}`;
            state.isPlaying = false;
            state.currentIndex = -1;
            updateQueueDisplay();
        }
    }

    // --- Event Listeners ---
    function setupEventListeners() {
        const state = window.audioPlayerGlobalState;
        if (!state.playerElement || !state.startButtonElement) {
            console.error("player.js: Cannot setup listeners, elements missing.");
            return;
        }
        console.log("player.js: Setting up event listeners...");

        // Audio Ended Event
        state.playerElement.addEventListener('ended', function() {
            const finishedAudioName = state.audioQueue[0]?.name || "Unknown"; // Get name *before* shifting
            console.log(`player.js: 'ended' event for: ${finishedAudioName}`);
            state.isPlaying = false; // Mark as not playing *before* potentially starting next

            if (state.audioQueue.length > 0) {
                state.audioQueue.shift(); // Remove the completed item from the FRONT
            }
            state.currentIndex = -1; // Reset index as the queue has shifted
            state.statusElement.textContent = `Finished: ${finishedAudioName}. Checking queue...`;
            updateQueueDisplay(); // Update list display

            // Check if more items exist and play next
            if (state.audioQueue.length > 0) {
                console.log("player.js: Queue has more items. Calling playNextInQueue() soon...");
                // Use a small delay to prevent potential race conditions or browser issues
                setTimeout(playNextInQueue, 150);
            } else {
                console.log("player.js: Queue empty after playback.");
                state.statusElement.textContent = 'Queue finished.';
                // updateQueueDisplay() already handled button state
            }
        });

        // Player Error Event
        state.playerElement.addEventListener('error', function(e) {
             const errorAudioName = state.audioQueue[0]?.name || "Unknown";
             console.error(`player.js: 'error' event for ${errorAudioName}:`, state.playerElement.error);
             state.statusElement.textContent = `Error playing ${errorAudioName}: ${state.playerElement.error?.message || 'Unknown Error'}`;
             state.isPlaying = false;
             state.currentIndex = -1;
             // Decide how to handle error (e.g., skip to next)
             if (state.audioQueue.length > 0) {
                 state.audioQueue.shift(); // Remove the problematic item
             }
             updateQueueDisplay();
             // Try next if available
             if (state.audioQueue.length > 0) {
                 setTimeout(playNextInQueue, 150);
             }
        });


        // Start Button Event
        state.startButtonElement.addEventListener('click', function() {
            console.log("player.js: Start button clicked.");
            if (state.audioQueue.length > 0 && !state.isPlaying) {
                playNextInQueue(); // Start playing the queue
            } else if (state.audioQueue.length === 0) {
                state.statusElement.textContent = "Queue is empty. Add audio first.";
            } else if (state.isPlaying) {
                state.statusElement.textContent = "Already playing."; // Or implement pause/resume logic here
            }
        });

         console.log("player.js: Event listeners set up.");
    }


    // --- Interface for Gradio ---
    // This object will hold functions callable from Python via returned JS
    window.audioPlayerInterface = {
        /**
         * Adds a batch of audio items to the queue.
         * @param {Array<Object>} items - Array of audio objects {src: "data:...", name: "..."}
         */
        addAudioBatch: function(items) {
            const state = window.audioPlayerGlobalState;
            if (!state.isInitialized) {
                console.warn("player.js: addAudioBatch called before initialization. Queueing data is not implemented, data might be lost.");
                // Optionally, could store in a temporary queue until initialized
                return;
            }
            if (!Array.isArray(items)) {
                console.error("player.js: addAudioBatch received non-array data:", items);
                return;
            }

            console.log(`player.js: addAudioBatch called with ${items.length} item(s).`);
            let addedCount = 0;
            items.forEach(item => {
                if (item && item.src && item.name) {
                    // Basic check to prevent adding duplicates if needed (optional)
                    // if (!state.audioQueue.some(existing => existing.src === item.src)) {
                         state.audioQueue.push(item);
                         addedCount++;
                    // } else {
                    //     console.log(`player.js: Skipping duplicate: ${item.name}`);
                    // }
                } else {
                    console.warn("player.js: Invalid item format in addAudioBatch:", item);
                }
            });

            if (addedCount > 0) {
                console.log(`player.js: Added ${addedCount} items. Queue size: ${state.audioQueue.length}`);
                state.statusElement.textContent = `Added ${addedCount} audio(s) (Total: ${state.audioQueue.length})`;
                updateQueueDisplay(); // Update the visual queue list

                // **** Auto-play trigger ****
                // If items were added AND the player is not currently playing, start the queue.
                if (!state.isPlaying && state.audioQueue.length > 0) { // Check length again in case adds failed
                    console.log("player.js: New items added & not playing. Triggering auto play...");
                    // Delay slightly to ensure DOM updates from updateQueueDisplay are processed
                    setTimeout(playNextInQueue, 100);
                }
            }
        },

        // Example of another potential function callable from Python
        clearQueue: function() {
             const state = window.audioPlayerGlobalState;
             if (!state.isInitialized) return;
             console.log("player.js: clearQueue called.");
             state.audioQueue = [];
             state.isPlaying = false;
             state.currentIndex = -1;
             state.playerElement.pause();
             state.playerElement.src = ""; // Clear source
             state.statusElement.textContent = "Queue cleared.";
             updateQueueDisplay();
        }
    };

    // --- Initialization ---
    function initializePlayer() {
        console.log("player.js: DOM ready or script loaded, initializing player elements...");
        const state = window.audioPlayerGlobalState;

        // Check if already initialized to prevent duplicate setups
        if (state.isInitialized) {
            console.log("player.js: Already initialized.");
            return;
        }

        state.playerElement = document.getElementById('persistent-player');
        state.statusElement = document.getElementById('player-status');
        state.startButtonElement = document.getElementById('start-queue-button');
        state.queueListElement = document.getElementById('queue-list');
        // state.commElement = document.getElementById('streamlit-comm'); // Removed

        if (!state.playerElement || !state.statusElement || !state.startButtonElement || !state.queueListElement) {
            console.error("player.js: FATAL - One or more essential player elements not found in the DOM! Aborting init.");
            // Maybe display an error message in the UI if possible
             try {
                let body = document.querySelector('body');
                if (body) {
                    let errDiv = document.createElement('div');
                    errDiv.style.color = 'red';
                    errDiv.textContent = 'Error: Player HTML elements missing. Cannot initialize player.';
                    body.prepend(errDiv); // Add error at top
                }
             } catch(e){}
            return; // Stop initialization
        }

        state.isInitialized = true; // Mark as initialized *after* finding elements
        console.log("player.js: Player elements found and assigned.");

        // No initial data to process from a hidden div anymore

        setupEventListeners(); // Setup listeners for player events and button clicks
        updateQueueDisplay(); // Initial display update (will show "Queue is empty")

        console.log("player.js: Initialization complete. Waiting for audio data via audioPlayerInterface.");
        state.statusElement.textContent = "Player ready. Add audio to the queue."; // Set initial status
    }

    // --- Run Initialization ---
    // Use DOMContentLoaded to ensure HTML is parsed, but also run immediately if already loaded.
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializePlayer);
    } else {
        // DOMContentLoaded has already fired
        console.log("player.js: DOM already loaded, running initializePlayer directly.");
        initializePlayer();
    }

} else {
    console.log("player.js: Global state already exists. Skipping re-initialization.");
    // If re-running script somehow, maybe re-run init if needed, but check element existence first.
    // if (!window.audioPlayerGlobalState.isInitialized) {
    //    console.log("player.js: Re-running initialization logic as state exists but not marked initialized.");
    //    initializePlayer(); // Be cautious with this, might lead to double listeners if not careful
    // }
}