#-*- coding: utf-8 -*-
import os
import base64
import tempfile
from odoo.exceptions import UserError
from odoo import api, fields, models, _, SUPERUSER_ID
import xlrd



class ImportProductVariant(models.TransientModel):
    _name = "wizard.import.product.variant"

    file_data = fields.Binary('Archive', required=True,)
    file_name = fields.Char('File Name')
    # res_ids = fields.Integer('Resource IDs', readonly=True,)



    def import_button(self):
        if not self.csv_validator(self.file_name):
            raise UserError(_("The file must be an .xls/.xlsx extension"))

        file_path = tempfile.gettempdir() + '/file.xlsx'
        data = self.file_data
        f = open(file_path, 'wb')
        f.write(base64.b64decode(data))
        #f.write(data.decode('base64'))
        f.close()
        workbook = xlrd.open_workbook(file_path, on_demand=True)
        worksheet = workbook.sheet_by_index(0)
        # Number of columns
        num_cols = worksheet.ncols
        # header
        headers = []
        for col_idx in range(0, num_cols):
            cell_obj = worksheet.cell(0, col_idx)
            headers.append(cell_obj.value)

        name_field = False
        headers_lower = []
        attributes_dict = {}
        fields_dict = {}
        template_attributes = {}
        tag_att = {}
        attribute_obj = self.env['product.attribute']
        tag_obj = self.env['product.tag']
        count_items=[]
        count_variant=[]
        count_edit=[]
        item_edit=[]
        x=0
        last_id = self.env['product.product'].search([], order='id desc', limit=1).id
        new_id = last_id
        create=0
        ndx=new_id
        attribute_value_obj = self.env['product.attribute.value']
        i = 0
        product_idx = None
        for h in headers:
            lower = h.lower()
            headers_lower.append(lower)
            lower_split = lower.split(':') if lower else ''
            if lower == 'name':
                name_field = True
                fields_dict[i] = lower
                product_idx = i
            elif len(lower_split) == 2 and lower_split[0].strip() == 'attribute':
                attribute_name = h.split(':')[1].strip()
                attribute = attribute_obj.search([('name','=',attribute_name)],limit=1)
                if not attribute:
                    attribute = attribute_obj.create({'name':attribute_name})
                attributes_dict[i] = attribute.id
            elif len(lower_split) == 1:
                fields_dict[i] = lower
            else:
                raise UserError(_('Invalid column name'))
            i += 1

        if not name_field:
            raise UserError(_('No name field found!'))
        import_data = {}
        for row_idx in range(1, worksheet.nrows):
            # Iterate through rows
            row_dict = {}
            product_name = None
            values = {}
            attribute_values = []
            for col_idx in range(0, num_cols):  # Iterate through columns
                cell_obj = worksheet.cell(row_idx, col_idx)  # Get cell object by row, col

                if not cell_obj.value:
                    raise UserError(_('Empty Row value!'))
                if cell_obj.value:

                    if col_idx in fields_dict:
                        field_name = fields_dict[col_idx]
                        values[field_name] = cell_obj.value
                        if col_idx == product_idx :
                            product_name = values[field_name]
                            product2 = self.env['product.product'].search([('name', '=', product_name)])
                            if product2:
                                count_edit = list(set(count_edit + product2.ids))



                        elif fields_dict[col_idx] == 'barcode':
                            values[field_name] = str(cell_obj.value)
                        elif fields_dict[col_idx] == 'default_code':
                            values[field_name] = str(cell_obj.value)
                        elif fields_dict[col_idx] == 'season_id':
                            season_id=self.env['product.season'].search([('name','=',cell_obj.value)])
                            if not season_id:
                                season_id = self.env['product.season'].create({'name':cell_obj.value})
                            values[field_name] = season_id.id

                        elif fields_dict[col_idx] == 'categ_id':
                            category=self.env['product.category'].search([('name','=',cell_obj.value)])
                            if not category:
                                raise UserError(_('Product category %s not exist!' %cell_obj.value))
                            else:    # season_id = self.env['product.season'].create({'name':cell_obj.value})
                                values[field_name] = category.id
                        elif fields_dict[col_idx] == 'tag_ids':
                            tags = cell_obj.value.split(',')
                            tag_ids = []
                            for t in tags:
                                tag_opj = tag_obj.search([('name', '=', t)], limit=1)
                                if tag_opj:
                                    tag_ids.append(tag_opj.id)
                                else:
                                    tag_opj = self.env['product.tag'].create({'name': t})
                                    tag_ids.append(tag_opj.id)

                            product = self.env['product.product'].search([('name', '=',product_name)]).ids
                            if x >= len(product):
                                x=0
                            if product:
                                tag_att[product[x]] = tag_ids
                                new_id = ndx = product[x]
                                x +=1

                            else:
                                new_id += 1
                                tag_att[new_id] = tag_ids


                            values[field_name]=tag_ids
                    elif col_idx in attributes_dict:
                        attribute_id = attributes_dict[col_idx]
                        attribute_value_name = cell_obj.value
                        attribute_value = attribute_value_obj.search([('name','=',str(attribute_value_name)),('attribute_id','=',attribute_id)])
                        if not attribute_value:
                            attribute_value = attribute_value_obj.create({'name':str(attribute_value_name),'attribute_id':attribute_id})
                        attribute_values.append(attribute_value.id)
                        if product_name:
                            if not product_name in template_attributes:
                                template_attributes[product_name] = {}
                            if attribute_id and not attribute_id in template_attributes[product_name]:
                                template_attributes[product_name][attribute_id] = []
                            template_attributes[product_name][attribute_id].append(attribute_value.id)

                if col_idx == (num_cols -1):
                    if not product_name:
                        raise UserError(_('Empty Product Name!'))
                    if product_name not in import_data:
                        import_data[product_name] = {}

                    attribute_values = list(set(attribute_values.copy()))

                    import_data[product_name][tuple(attribute_values)] = values.copy()



        x = 0
        print("import_data == ",import_data)

        for prod_name in import_data:
            product_templ = self.env['product.template'].search([('name','=',prod_name)])
            if not product_templ:
                print('0000 prod_name',prod_name)
                vals = {}
                vals['name'] = prod_name
                vals['attribute_line_ids'] = []
                if prod_name in template_attributes:
                    for tmp_attrib in template_attributes[prod_name]:
                        vals['attribute_line_ids'].append(
                            (0, 0, {'attribute_id': tmp_attrib,
                                    'value_ids': [], })
                        )

                        for att_val in set(template_attributes[prod_name][tmp_attrib]):
                            vals['attribute_line_ids'][-1][2]['value_ids'].append((4, att_val))

                product_templ = self.env['product.template'].create(vals)

                if product_templ.id not in count_items:

                    count_items.append(product_templ.id)


            else:
                print('1111 prod_name', prod_name)
                temp_atts  = product_templ.attribute_line_ids.mapped('attribute_id')
                print("temp_atts == ",temp_atts)
                print("template_attributes == ",template_attributes)
                for tmp_attrib in template_attributes[prod_name]:
                    tmp_att_vals = []
                    for att_val in set(template_attributes[prod_name][tmp_attrib]):
                        tmp_att_vals.append((4, att_val))
                    if tmp_attrib not in temp_atts.ids:
                        vals = {
                            'product_tmpl_id': product_templ.id,
                            'attribute_id': tmp_attrib,
                            'value_ids': tmp_att_vals,
                        }
                        # self.env['product.template.attribute.line'].create({
                        #     'product_tmpl_id': product_templ.id,
                        #     'attribute_id': tmp_attrib,
                        #     'value_ids': tmp_att_vals,
                        # })

                        product_templ.write({'attribute_line_ids':[(0,0,vals)]})
                        product_templ.write({'attribute_line_ids':[(0,0,vals)]})
                    else:
                        for att_tmpl_line in product_templ.attribute_line_ids:
                            if att_tmpl_line.attribute_id.id == tmp_attrib:
                                att_tmpl_line.write({'value_ids': tmp_att_vals})
                                break

                product_templ.create_variant_ids()
                if product_templ.id not in item_edit:
                    item_edit.append(product_templ.id)


            lst_vrnt=product_templ.product_variant_ids.ids
            if lst_vrnt not in count_variant and count_items:
                count_variant = list(set(count_variant + lst_vrnt))
            for prod in product_templ.product_variant_ids:
                print("prod == ",prod)
                print("prod Barcode== ",prod.barcode)
                if tag_att:
                    if new_id == ndx and create== 0:
                        prod.write({'tag_ids' :[(6, 0,tag_att[prod.id])] })
                    else:
                        ndx = ndx + 1
                        prod.write({'tag_ids': [(6, 0, tag_att[ndx])]})
                        create=1

                prod_att_values = set(prod.attribute_value_ids.ids or [])
                print('prod_att_values == ', prod_att_values)
                print('import_data[code].keys()  == ', import_data[prod_name].keys)
                for att_value_ids in import_data[prod_name].keys():
                    print("att_value_ids == ",att_value_ids)
                    if set(prod_att_values) == set(att_value_ids):
                        product_values = import_data[prod_name][att_value_ids]
                        prod.write(product_values.copy())
        print("  => ", row_idx)
        context = dict(self._context) or {}
        context['default_count_variant'] = len(count_variant)
        context['default_count_items'] = len(count_items)
        context['default_count_edit'] = len(count_edit)
        context['default_count_items_edit'] = len(item_edit)
        return {
            'name': 'Import Resalt',
            'type': 'ir.actions.act_window',
            'res_model': 'wizard.resalt.variant',
            'view_mode': 'form',
            'view_type': 'form',
            'view_id': self.env.ref('import_product_variant.resalt_import_product_variant').id,
            'context': context,
            'target': 'new',
        }

    @api.model
    def csv_validator(self, xml_name):
        name, extension = os.path.splitext(xml_name)
        return True if extension == '.xls' or extension == '.xlsx' else False

