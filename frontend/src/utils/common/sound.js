import saveSrc from '@/assets/sounds/on-save.mp3'
import deleteSrc from '@/assets/sounds/on-delete.mp3'
import otherSrc from '@/assets/sounds/other.mp3'

// Short cues that go with a toast or popup:
//   save   - a record was saved / created / updated
//   delete - a delete, a warning, an error, or an "are you sure" popup
//   other  - everything else (chat, assignments, new mail, general info)
const SOURCES = { save: saveSrc, delete: deleteSrc, other: otherSrc }
const players = {}

export function playSound(kind) {
  const src = SOURCES[kind]
  if (!src || typeof Audio === 'undefined') return
  try {
    const audio = (players[kind] ||= new Audio(src))
    audio.currentTime = 0
    // Browsers refuse audio before the first click on the page; a refused cue must never break a toast.
    audio.play()?.catch(() => {})
  } catch {
    /* no audio support */
  }
}
