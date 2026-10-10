// jsdom has no audio playback: sound cues call play(), so make it a quiet no-op.
window.HTMLMediaElement.prototype.play = () => Promise.resolve()
window.HTMLMediaElement.prototype.pause = () => {}
