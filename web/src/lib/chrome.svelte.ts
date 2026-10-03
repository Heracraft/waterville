// Page chrome shared across components that do not own each other:
// Chat sets modal while the narrow-screen source panel covers the page, and
// Header goes inert with it.
// A page that owns a chat sets newChat while a conversation is open, and the
// staff layout shows the header's New chat button for it (as the public page does).
export const chrome = $state<{ modal: boolean; newChat: (() => void) | null }>({ modal: false, newChat: null });
