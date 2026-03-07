const versionDate = new Date().toISOString().slice(0, 10);

module.exports = {
  pdf_options: {
    format: 'A4',
    margin: { top: '38mm', right: '18mm', bottom: '20mm', left: '18mm' },
    displayHeaderFooter: true,

    headerTemplate: `
      <style>
        header {
          align-items: center;
          color: #666;
          display: flex;
          font-family: sans-serif;
          font-size: 9pt;
          justify-content: space-between;
          padding: 8mm 18mm;
          width: 100%;
        }

        header svg {
          height: 1.5cm;
          width: auto;
        }
      </style>
      <header>
        <div><!--INLINE_LOGO_MARKUP--></div>
        <em>ver. ${versionDate}</em>
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
