const versionDate = new Date().toISOString().slice(0, 10);

module.exports = {
  pdf_options: {
    format: 'A4',
    margin: { top: '38mm', right: '18mm', bottom: '20mm', left: '18mm' },
    displayHeaderFooter: true,

    headerTemplate: `
      <style>
        header {
          color: #666;
          display: grid;
          font-family: sans-serif;
          font-size: 9pt;
          grid-template-columns: 1fr auto;
          padding: 8mm 18mm;
          width: 100%;
        }

        header svg {
          height: 1.5cm;
          width: auto;
        }

        .ver {
          text-align: right;
        }
      </style>
      <header>
        <div><!--INLINE_LOGO_MARKUP--></div>
        <div class="ver"><em>ver. ${versionDate}</em></div>
      </header>
    `,

    footerTemplate: `
      <style>
        footer {
          color: #666;
          font-family: sans-serif;
          font-size: 9pt;
          padding-bottom: 5mm;
          text-align: center;
          width: 100%;
        }
      </style>
      <footer>
        Page <span class="pageNumber"></span> / <span class="totalPages"></span>
      </footer>
    `
  }
};
