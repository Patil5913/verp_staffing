// The signed-in user's roles, from the boot data the server renders into the
// page (www/verp.py get_boot). UX only — a hidden button or a read-only field
// is never the security boundary; the server enforces every write.

export const isAdministrator = () => window.user === 'Administrator'

export const hasRole = (role) => isAdministrator() || (Array.isArray(window.roles) && window.roles.includes(role))

export const isSystemManager = () => hasRole('System Manager')
