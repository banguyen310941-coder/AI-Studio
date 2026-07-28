from PySide6.QtWidgets import QApplication


def apply_styles(app: QApplication) -> None:
    app.setStyleSheet(
        """
        QMainWindow {
            background: #f4f5f7;
        }

        #sidebar {
            background: #17191f;
        }

        #logo {
            color: white;
            font-size: 22px;
            font-weight: 700;
            padding: 12px;
        }

        #menuButton {
            background: transparent;
            color: #d8dbe2;
            border: none;
            border-radius: 8px;
            padding: 12px 14px;
            text-align: left;
            font-size: 14px;
        }

        #menuButton:hover {
            background: #2b2f39;
            color: white;
        }

        #menuButton[active="true"] {
            background: #3b5bfd;
            color: white;
        }

        #version {
            color: #777d8a;
            font-size: 12px;
        }

        #content {
            background: #f4f5f7;
        }

        #pageTitle {
            color: #17191f;
            font-size: 30px;
            font-weight: 700;
        }

        #description {
            color: #626875;
            font-size: 15px;
        }

        #primaryButton {
            background: #3b5bfd;
            color: white;
            border: none;
            border-radius: 8px;
            padding: 12px 18px;
            font-size: 14px;
            font-weight: 600;
        }

        #primaryButton:hover {
            background: #2946d7;
        }

        #card {
            background: white;
            border: 1px solid #e1e4ea;
            border-radius: 12px;
        }

        #cardTitle {
            color: #17191f;
            font-size: 18px;
            font-weight: 700;
        }

        #cardText {
            color: #555b67;
            font-size: 14px;
        }
#projectButton {
    background: white;
    color: #17191f;
    border: 1px solid #e1e4ea;
    border-radius: 8px;
    padding: 12px 14px;
    text-align: left;
    font-size: 14px;
}

#projectButton:hover {
    background: #eef1ff;
    border: 1px solid #3b5bfd;
}
        QStatusBar {
            background: white;
            color: #555b67;
        }

        QListWidget, QPlainTextEdit, QTextEdit, QComboBox, QDoubleSpinBox {
            background: white;
            color: #17191f;
            border: 1px solid #d9dde6;
            border-radius: 8px;
            padding: 7px;
            selection-background-color: #3b5bfd;
        }

        QPushButton {
            min-height: 28px;
        }

        QProgressBar {
            background: #e7eaf0;
            border: none;
            border-radius: 7px;
            height: 14px;
            text-align: center;
        }

        QProgressBar::chunk {
            background: #3b5bfd;
            border-radius: 7px;
        }

        #dashboardScroll {
            background: #f4f5f7;
            border: none;
        }

        #sectionTitle {
            color: #17191f;
            font-size: 20px;
            font-weight: 700;
        }

        #statCard, #actionCard {
            background: white;
            border: 1px solid #e1e4ea;
            border-radius: 12px;
        }

        #statLabel {
            color: #6b7280;
            font-size: 13px;
            font-weight: 600;
        }

        #statValue {
            color: #17191f;
            font-size: 28px;
            font-weight: 800;
        }

        #statHint, #projectMeta {
            color: #8a909c;
            font-size: 12px;
        }

        #actionIcon {
            font-size: 26px;
        }

        #actionTitle, #projectName {
            color: #17191f;
            font-size: 16px;
            font-weight: 700;
        }

        #secondaryButton {
            background: #eef1ff;
            color: #2946d7;
            border: 1px solid #d8defe;
            border-radius: 8px;
            padding: 8px 14px;
            font-weight: 600;
        }

        #secondaryButton:hover {
            background: #dfe5ff;
            border-color: #3b5bfd;
        }

        #projectRow {
            background: #fbfcff;
            border: 1px solid #e6e9f0;
            border-radius: 10px;
        }

        #projectRow:hover {
            background: #f3f5ff;
            border-color: #cbd3ff;
        }
        """
    )