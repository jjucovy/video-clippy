/**
 * LEGACY: Video.js player utilities for Cloudflare Stream HLS playback.
 * Only used for non-R2 videos during migration. Will be removed in Phase 7
 * when all content is migrated to R2 plain MP4 playback.
 */

const VIDEOJS_VERSION = '8.6.1';
const VIDEOJS_CDN_URL = `https://vjs.zencdn.net/${VIDEOJS_VERSION}/video.min.js`;

export interface VideoJsPlayerOptions {
  playerId: string;
  startTime?: number;
  endTime?: number;
  autoLoopToStart?: boolean; // For carousel clips: auto-loop to start when reaching end
  remapTimeline?: boolean; // Hide full video timeline, show only clip as standalone (HACK until Cloudflare Clips API)
}

/**
 * Loads Video.js library if not already loaded
 * Returns a promise that resolves when Video.js is ready
 */
export function loadVideoJs(): Promise<void> {
  return new Promise((resolve, reject) => {
    if (typeof videojs !== 'undefined') {
      resolve();
      return;
    }

    const script = document.createElement('script');
    script.src = VIDEOJS_CDN_URL;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error('Failed to load Video.js library'));
    document.head.appendChild(script);
  });
}

/**
 * Initialize a Video.js player with clip boundary support
 */
export async function initializeVideoJsPlayer(options: VideoJsPlayerOptions): Promise<any> {
  const { playerId, startTime, endTime, autoLoopToStart = false, remapTimeline = false } = options;

  await loadVideoJs();

  const videoElement = document.getElementById(playerId);
  if (!videoElement) {
    throw new Error(`Video element with id "${playerId}" not found`);
  }

  const player = videojs(videoElement);

  return new Promise((resolve) => {
    player.ready(() => {
      console.log('Video.js player ready:', playerId);

      // Helper to set start time
      const applyStartTime = () => {
        if (startTime !== undefined && !isNaN(startTime) && startTime > 0) {
          console.log('Setting start time to:', startTime);
          player.currentTime(startTime);
        }
      };

      // Helper to apply timeline remapping
      const applyTimelineRemap = () => {
        if (remapTimeline && startTime !== undefined && endTime !== undefined) {
          console.log('Will remap timeline for:', playerId, 'Start:', startTime, 'End:', endTime);
          setTimeout(() => {
            remapTimelineToClip(player, startTime, endTime);
          }, 100);
        }
      };

      // Set start time when video is loaded
      player.on('loadedmetadata', () => {
        console.log('Metadata loaded for:', playerId);
        applyStartTime();
        applyTimelineRemap();
      });

      // Also check if metadata is already loaded (race condition fix)
      // readyState >= 1 means HAVE_METADATA or higher
      if (player.readyState() >= 1) {
        console.log('Metadata already loaded for:', playerId);
        applyStartTime();
        applyTimelineRemap();
      }

      // Handle clip boundaries
      if (endTime !== undefined && !isNaN(endTime) && endTime > 0) {
        setupClipBoundaries(player, startTime || 0, endTime, autoLoopToStart);
      }

      // Error handling
      player.on('error', (e: any) => {
        console.error('Video.js error for', playerId, ':', e, player.error());
      });

      resolve(player);
    });
  });
}

/**
 * Format seconds to MM:SS or HH:MM:SS
 */
function formatTime(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);

  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }
  return `${minutes}:${secs.toString().padStart(2, '0')}`;
}

/**
 * HACK: Remap video.js timeline to show clip as standalone video
 * Makes a clip appear independent by hiding the full source video duration
 *
 * This is a workaround until we implement Cloudflare Stream Clips API.
 * The proper solution creates real clips with their own UIDs.
 */
function remapTimelineToClip(player: any, clipStart: number, clipEnd: number) {
  const clipDuration = clipEnd - clipStart;
  console.log('🎬 Remapping timeline - Clip duration:', clipDuration, 'Start:', clipStart, 'End:', clipEnd);
  console.log('🎬 Player control bar:', player.controlBar);
  console.log('🎬 Duration display:', player.controlBar?.durationDisplay);
  console.log('🎬 Current time display:', player.controlBar?.currentTimeDisplay);

  // Override duration display to show clip duration instead of full video
  const durationDisplay = player.controlBar?.durationDisplay;
  if (durationDisplay) {
    console.log('🎬 Overriding duration display updateContent method');
    const originalUpdateContent = durationDisplay.updateContent;
    durationDisplay.updateContent = function() {
      // Always show clip duration regardless of actual video duration
      const formattedTime = formatTime(clipDuration);
      this.formattedTime_ = formattedTime;
      this.contentEl().textContent = formattedTime;
    };
    // Trigger initial update
    durationDisplay.updateContent();
  }

  // Override current time display to show relative time (0:00 at clip start)
  const currentTimeDisplay = player.controlBar?.currentTimeDisplay;
  if (currentTimeDisplay) {
    console.log('🎬 Overriding current time display updateContent method');
    const originalUpdateContent = currentTimeDisplay.updateContent;
    currentTimeDisplay.updateContent = function() {
      const actualTime = player.currentTime();
      const relativeTime = Math.max(0, Math.min(actualTime - clipStart, clipDuration));
      const formattedTime = formatTime(relativeTime);
      this.formattedTime_ = formattedTime;
      this.contentEl().textContent = formattedTime;
    };
    // Trigger initial update
    currentTimeDisplay.updateContent();
  }

  // Override progress bar behavior
  const progressControl = player.controlBar?.progressControl;
  const seekBar = progressControl?.seekBar;

  console.log('🎬 Progress control:', progressControl);
  console.log('🎬 Seek bar:', seekBar);

  if (seekBar) {
    console.log('🎬 Setting up progress bar overrides...');

    // Store original methods
    const originalGetPercent = seekBar.getPercent.bind(seekBar);
    const originalHandleMouseMove = seekBar.handleMouseMove.bind(seekBar);

    // Override getPercent to show progress through clip only
    seekBar.getPercent = function() {
      const currentTime = player.currentTime();
      const relativeTime = Math.max(0, Math.min(currentTime - clipStart, clipDuration));
      const percent = relativeTime / clipDuration;
      return Math.max(0, Math.min(percent, 1)); // Clamp to 0-1
    };

    // Override handleMouseMove for seeking within clip
    seekBar.handleMouseMove = function(event: any) {
      const distance = this.calculateDistance(event);
      const newTime = clipStart + (distance * clipDuration);

      // Clamp to clip boundaries
      const clampedTime = Math.max(clipStart, Math.min(newTime, clipEnd));
      player.currentTime(clampedTime);
    };

    // Also need to handle mouse down for seeking
    const originalHandleMouseDown = seekBar.handleMouseDown?.bind(seekBar);
    if (originalHandleMouseDown) {
      seekBar.handleMouseDown = function(event: any) {
        // Call original to set up dragging state
        originalHandleMouseDown(event);

        // Then handle the seek
        const distance = this.calculateDistance(event);
        const newTime = clipStart + (distance * clipDuration);
        const clampedTime = Math.max(clipStart, Math.min(newTime, clipEnd));
        player.currentTime(clampedTime);
      };
    }
  }

  // Update load progress bar to show clip range
  const loadProgressBar = progressControl?.loadProgressBar;
  if (loadProgressBar) {
    const originalUpdate = loadProgressBar.update?.bind(loadProgressBar);
    if (originalUpdate) {
      loadProgressBar.update = function() {
        // Call original update
        originalUpdate();

        // Adjust the width to represent clip portion
        const buffered = player.buffered();
        if (buffered && buffered.length > 0) {
          const bufferedEnd = buffered.end(buffered.length - 1);
          const bufferedStart = buffered.start(0);

          // Calculate how much of the clip is buffered
          const clipBufferedEnd = Math.min(bufferedEnd, clipEnd);
          const clipBufferedStart = Math.max(bufferedStart, clipStart);
          const clipBufferedAmount = Math.max(0, clipBufferedEnd - clipBufferedStart);
          const bufferedPercent = (clipBufferedAmount / clipDuration) * 100;

          const el = this.el();
          if (el) {
            el.style.width = `${bufferedPercent}%`;
          }
        }
      };
    }
  } else {
    console.warn('🎬 Seek bar not found, progress bar overrides skipped');
  }

  console.log('🎬 Timeline remapping complete!');
}

/**
 * Set up clip time boundaries with optional auto-loop
 */
function setupClipBoundaries(
  player: any,
  clipStartTime: number,
  clipEndTime: number,
  autoLoopToStart: boolean
) {
  console.log('Setting up clip boundaries - Start:', clipStartTime, 'End:', clipEndTime, 'Auto-loop:', autoLoopToStart);

  let hasReachedEnd = false;
  let isAutoSeeking = false;

  // Primary end time check
  player.on('timeupdate', () => {
    if (isAutoSeeking) return; // Skip during auto-seek operations

    const currentTime = player.currentTime();
    if (currentTime >= clipEndTime && !hasReachedEnd) {
      hasReachedEnd = true;
      console.log('Reached end time, pausing');
      player.pause();

      if (autoLoopToStart) {
        // Auto seek back to start after a brief pause
        setTimeout(() => {
          isAutoSeeking = true;
          console.log('Auto-looping to start:', clipStartTime);
          player.currentTime(clipStartTime);
          setTimeout(() => {
            isAutoSeeking = false;
            hasReachedEnd = false;
          }, 100);
        }, 500);
      }
    }
  });

  // Prevent seeking outside clip boundaries
  player.on('seeking', () => {
    if (isAutoSeeking) return; // Allow our auto-seek

    const seekTime = player.currentTime();
    console.log('User seeking to:', seekTime, 'Clip range:', clipStartTime, '-', clipEndTime);

    if (seekTime < clipStartTime) {
      console.log('Preventing seek before clip start, redirecting to:', clipStartTime);
      player.currentTime(clipStartTime);
      hasReachedEnd = false; // Reset flag so timeupdate can catch end boundary again
    } else if (seekTime > clipEndTime) {
      console.log('Preventing seek after clip end, redirecting to:', clipEndTime);
      player.currentTime(clipEndTime);
      hasReachedEnd = false; // Reset flag so timeupdate can catch end boundary again
    } else {
      // Valid seek within clip range
      hasReachedEnd = false;
    }
  });

  // Handle manual play after reaching end
  if (autoLoopToStart) {
    player.on('play', () => {
      if (hasReachedEnd && !isAutoSeeking) {
        console.log('Play after end reached, seeking to start');
        isAutoSeeking = true;
        player.currentTime(clipStartTime);
        setTimeout(() => {
          isAutoSeeking = false;
          hasReachedEnd = false;
        }, 100);
      }
    });
  }
}

/**
 * Initialize all video players on the page with data attributes
 * Useful for static components that don't need dynamic initialization
 */
export async function initializeAllVideoPlayers() {
  await loadVideoJs();

  const videos = document.querySelectorAll<HTMLVideoElement>('video[data-stream-id]');
  console.log('Found videos:', videos.length);

  const promises = Array.from(videos).map(async (videoElement) => {
    const playerId = videoElement.id;
    const startTime = parseFloat(videoElement.dataset.startTime || '0');
    const endTime = parseFloat(videoElement.dataset.endTime || '0');

    try {
      await initializeVideoJsPlayer({
        playerId,
        startTime: !isNaN(startTime) ? startTime : undefined,
        endTime: !isNaN(endTime) ? endTime : undefined,
        autoLoopToStart: false, // Default behavior for standalone players
      });
    } catch (error) {
      console.error('Error initializing Video.js for', playerId, ':', error);
    }
  });

  await Promise.all(promises);
}
