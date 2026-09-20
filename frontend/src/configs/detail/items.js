export const itemConfig = {
  doctype: 'Item',
  timeline: 'full',
  readOnlyFields: (d) => (d.isNew.value ? [] : ['item_name']),
  tabs: [
    {
      key: 'details',
      label: 'Details',
      sections: [{ type: 'fields', title: 'Item', fieldnames: ['item_name', 'item_category', 'stock_uom', 'is_service', 'disabled'] }],
    },
  ],
}

export const itemCategoryConfig = {
  doctype: 'Item Category',
  timeline: 'full',
  readOnlyFields: (d) => (d.isNew.value ? [] : ['item_category_name']),
  tabs: [
    {
      key: 'details',
      label: 'Details',
      sections: [{ type: 'fields', title: 'Item Category', fieldnames: ['item_category_name', 'parent_item_category', 'is_group'] }],
    },
  ],
}

export const uomConfig = {
  doctype: 'UOM',
  timeline: 'full',
  readOnlyFields: (d) => (d.isNew.value ? [] : ['uom_name']),
  tabs: [
    {
      key: 'details',
      label: 'Details',
      sections: [{ type: 'fields', title: 'Unit of Measure', fieldnames: ['uom_name', 'enabled', 'must_be_whole_number'] }],
    },
  ],
}
