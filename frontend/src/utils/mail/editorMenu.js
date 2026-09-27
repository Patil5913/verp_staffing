// Toolbar for composing mail: text style, fonts, colour, lists, alignment, links.
const font = (label, family) => ({
  label,
  action: (e) => (family ? e.chain().focus().setFontFamily(family).run() : e.chain().focus().unsetFontFamily().run()),
  isActive: (e) => (family ? e.isActive('textStyle', { fontFamily: family }) : false),
})
const size = (label, px) => ({
  label,
  action: (e) => (px ? e.chain().focus().setFontSize(px).run() : e.chain().focus().unsetFontSize().run()),
  isActive: (e) => (px ? e.isActive('textStyle', { fontSize: px }) : false),
})

export const FONT_MENU = [
  font('Default font', null),
  font('Arial', 'Arial, Helvetica, sans-serif'),
  font('Verdana', 'Verdana, Geneva, sans-serif'),
  font('Tahoma', 'Tahoma, sans-serif'),
  font('Georgia', 'Georgia, serif'),
  font('Times New Roman', '"Times New Roman", Times, serif'),
  font('Courier New', '"Courier New", monospace'),
]
export const SIZE_MENU = [size('Default size', null), size('Small', '12px'), size('Normal', '14px'), size('Large', '18px'), size('Huge', '24px')]

export const MAIL_MENU = [
  'Undo',
  'Redo',
  'Separator',
  FONT_MENU,
  SIZE_MENU,
  ['Paragraph', 'Heading 1', 'Heading 2', 'Heading 3'],
  'Separator',
  'Bold',
  'Italic',
  'Underline',
  'Strikethrough',
  'FontColor',
  'Separator',
  'Bullet List',
  'Numbered List',
  'Align Left',
  'Align Center',
  'Align Right',
  'Separator',
  'Link',
  'Image',
  'Blockquote',
  'Horizontal Rule',
]
