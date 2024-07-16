from aqt import mw, utils, browser
from aqt.qt import *
from os.path import expanduser, join
from pickle import load, dump

import os
import re
import sys
import base64

# change template to include table
html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            img { max-width: 100%; }
            tr { page-break-inside:avoid; page-break-after:auto }
            td { page-break-after:auto; }
            td { border: 1px solid #ccc; padding: 1em; }
        {{style}}
        </style>
    </head>
    <body>
    <table cellspacing=10 width=100%>
    {{body}}
    </table>
    </body>
    </html>
"""

delimiter = "####"

class AddonDialog(QDialog):

    """Main Options dialog"""
    def __init__(self):
        QDialog.__init__(self, parent=mw)
        self.path = None
        self.deck = None
        self.fields = {}
        self.config_file = "export_decks_to_html_config.config"
        if os.path.exists(self.config_file):
            try:
                self.config = load(open(self.config_file, 'rb'))
            except:
                self.config = {}
        else:
            self.config = {}
        self._setup_ui()


    def _handle_button(self):
        dialog = OpenFileDialog()
        self.path = dialog.filename
        if self.path is not None:
            utils.showInfo("Choose file successful.")


    def _setup_ui(self):
        """Set up widgets and layouts"""
        layout = QGridLayout()
        layout.setSpacing(10)

        deck_label = QLabel("Choose deck")
        self.labels = []

        self.deck_selection = QComboBox()
        deck_names = sorted(mw.col.decks.allNames())
        current_deck = mw.col.decks.current()['name']
        deck_names.insert(0, current_deck)
        for i in range(len(deck_names)):
            if deck_names[i] == 'Default':
                deck_names.pop(i)
                break
        self.deck_selection.addItems(deck_names)
        self.deck_selection.currentIndexChanged.connect(self._select_deck)
        layout.addWidget(deck_label, 1, 0, 1, 1)
        layout.addWidget(self.deck_selection, 1, 1, 1, 2)

        css_label = QLabel('CSS')
        self.css_tb = QTextEdit(self)
        self.css_tb.resize(380,60)
        self.css_tb.setPlainText(self._setup_css())
        layout.addWidget(css_label, 2, 0, 1, 1)
        layout.addWidget(self.css_tb, 2, 1, 1, 2)

        html_label = QLabel('HTML')
        self.html_tb = QTextEdit(self)
        self.html_tb.resize(380,60)
        self.html_tb.setPlainText(self._setup_html())
        layout.addWidget(html_label, 3, 0, 1, 1)
        layout.addWidget(self.html_tb, 3, 1, 1, 2)

        # Main button box
        ok_btn = QPushButton("Export")
        save_btn = QPushButton("Save")
        cancel_btn = QPushButton("Cancel")

        button_box = QHBoxLayout()
        ok_btn.clicked.connect(self._on_accept)
        save_btn.clicked.connect(self._on_save)
        cancel_btn.clicked.connect(self._on_reject)
        button_box.addWidget(ok_btn)
        button_box.addWidget(save_btn)
        button_box.addWidget(cancel_btn)

        # Main layout
        main_layout = QVBoxLayout()
        main_layout.addLayout(layout)
        main_layout.addLayout(button_box)
        self.setLayout(main_layout)
        self.setMinimumWidth(360)
        self.setWindowTitle('Find words and create deck')


    def _select_deck(self):
        self.css_tb.setPlainText(self._setup_css())
        self.html_tb.setPlainText(self._setup_html())


    def _setup_css(self):
        deck = self.deck_selection.currentText()
        try:
            return self.config[deck]['css_text']
        except:
            return ""


    def _setup_html(self):
        template = ""
        template += '<td> \n'
        fields = self._select_fields(self.deck_selection.currentText())
        for idx, field in enumerate(fields):
            template += '<div class="field%d">{{%s}}</div>\n' % (idx, field)
        template += '</td> \n'
        return template


    def _on_save(self):
        self.config[self.deck_selection.currentText()] = {}
        self.config[self.deck_selection.currentText()]['html_text'] = self.html_tb.toPlainText()
        self.config[self.deck_selection.currentText()]['css_text'] = self.css_tb.toPlainText()
        dump(self.config, open(self.config_file, 'wb'))
        utils.showInfo("Config saved")


    def _convert_to_multiple_choices(self, value):
        choices = value.split("|")
        letters = "ABCDEFGHIKLMNOP"
        value = "<div>"
        for letter, choice in zip(letters, choices):
            value += '<div>' + "<span><strong>(" + letter + ")&nbsp</strong></span>" + choice.strip() + '</div>'
        return value + "</div>"


    def _select_fields(self, deck):
        query = 'deck:"{}"'.format(deck)
        try:
            card_id = mw.col.findCards(query=query)[0]
        except:
            utils.showInfo("This deck has no cards.")
            return []

        card = mw.col.getCard(card_id)

        note = card.note()
        model = note.model()
        fields = card.note().keys()
        return fields 

    def _on_accept(self):
        dialog = SaveFileDialog(self.deck_selection.currentText())
        path = dialog.filename
        if path == None:
            return
        deck = self.deck_selection.currentText()
        query = 'deck:"{}"'.format(deck)
        cids = mw.col.findCards(query=query)
        collection_path = mw.col.media.dir()
        if sys.version_info[0] >= 3:
            path = path[0]
        try:
            with open(path, "w", encoding="utf8") as f:
                html = ""
                template = self.html_tb.toPlainText()
                fields = re.findall("\{\{.*\}\}", template)
                for i, cid in enumerate(cids):
                    card_html = template
                    card_html = card_html.replace("{{id}}", str(i + 1))
                    card = mw.col.getCard(cid)
                    for fi, field in enumerate(fields):
                        anyFieldFound = False #to check if any field matched, otherwise show error message in exported file.
                        if field == "{{id}}":
                            continue
                        fieldNames = field[2:-2].split("//") #for decks that has multiple card types, e.g use {{Front//Text}} or {{Back//Extra}}
                        for fieldName in fieldNames:
                            try:
                                value = card.note()[fieldName]
                                value = re.sub(r'{{[c|C][0-9]+::(.*?)}}',r'\g<1>',value) # get rid of the cloze deletion formatting e.g. {{c1::someText}}
                                anyFieldFound = True
                                break
                            except:
                                continue
                        pictures = re.findall(r'src=["|' + "']" + "(.*?)['|" + '"]', value) #to find src='()' or src="()"
                        img_tmp01 = 'src="%s"'
                        img_tmp02 = "src='%s'"
                        if len(pictures):
                            for pic in pictures:
                                full_img_path = os.path.join(collection_path, pic)
                                with open(full_img_path, "rb") as image_file:
                                    encoded_string = base64.b64encode(image_file.read()).decode('ascii')
                                picture_b64 = 'data:image/jpeg;base64,' + encoded_string
                                value = value.replace(img_tmp01 % pic, img_tmp01 % picture_b64)
                                value = value.replace(img_tmp02 % pic, img_tmp02 % picture_b64)
                        card_html = card_html.replace("%s" % field, value)
                        value = ''
                    if anyFieldFound:
                        html += card_html
                    else:
                        html += '**************************************************************<br>\n'
                        html += 'Card Index:' + str(i + 1) + '<br>\n'
                        html += 'Card type not supported;<br>\n'
                        html += 'Edit the HTML Template to support these fields: ("' + '-'.join(card.note().keys()) + '").<br>\n'
                        html += '**************************************************************<br>\n'

                output_html = html_template.replace("{{style}}", self.css_tb.toPlainText())
                output_html = output_html.replace("{{body}}", html)
                f.write(output_html)
            utils.showInfo("Export to HTML successfully")
        except IOError as e:
            utils.showInfo(f"Error writing file: {str(e)}\nPlease choose a different filename or location.")


    def _on_reject(self):
        self.close()


class SaveFileDialog(QDialog):

    def __init__(self, filename):
        QDialog.__init__(self, mw)
        self.title='Save File'
        self.left = 10
        self.top = 10
        self.width = 640
        self.height = 480
        self.filename = None
        self.default_filename = filename
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle(self.title)
        self.setGeometry(self.left, self.top, self.width, self.height)
        self.filename = self._get_file()

    def _get_file(self):
        # options = QFileDialog.Options()
        options = QFileDialog.Option.DontUseNativeDialog
        # options |= QFileDialog.DontUseNativeDialog
        default_filename = self.default_filename.replace('::', '_')
        directory = os.path.join(expanduser("~/Desktop"), default_filename + ".html")
        try:
            path = QFileDialog.getSaveFileName(self, "Save File", directory, "All Files (*)", options=options)
            if path:
                return path
            else:
                utils.showInfo("Cannot open this file.")
        except:
            utils.showInfo("Cannot open this file.")
        return None


def display_dialog():
    dialog = AddonDialog()
    dialog.exec()
    
action = QAction("Export deck to html", mw)
action.setShortcut("Ctrl+M")
action.triggered.connect(display_dialog)
mw.form.menuTools.addAction(action)

