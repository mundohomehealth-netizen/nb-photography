NB PHOTOGRAPHY - WEBSITE
========================

PREVIEW
  Double-click index.html. Everything works locally except sending the
  inquiry form, which only works once the site is on Netlify.

PUT IT ONLINE (Netlify)
  1. Log in at app.netlify.com.
  2. Add a new site, choose "Deploy manually", and drag this whole
     folder (nb-photography-site) onto the upload area.
  3. Turn on the inquiry form: in the site's settings open Forms, click
     "Enable form detection", then drag the folder in again to redeploy.
  4. Get inquiries by email: Forms > Form notifications > add an Email
     notification for the "inquiry" form.
  5. Optional: Domain management > add your own domain.
  To update the site later, edit the files and drag the folder in again
  (Deploys > drag and drop).

THINGS TO EDIT (search index.html for "EDIT:")
  - Business name "NB Photography" (index.html, thank-you.html)
  - Location line "Toronto & destination"
  - About section text
  - Package prices and inclusions (placeholders)
  - Email address and Instagram handle in the contact section

ADDING PORTFOLIO PHOTOS
  Put resized images in assets/img/portfolio/ (about 800px and 1600px wide
  for the grid, 2400px for the full-screen view), then copy one <figure>
  block in the portfolio section and change the file names, alt text,
  caption and data-category (ceremony, portrait, couple or celebration).

FOLDERS
  index.html, thank-you.html   the pages
  assets/css/styles.css        colours and fonts are set at the top
  assets/js/album.js           the scroll-driven album
  assets/js/main.js            menu, filters, photo viewer
  frames/                      the album animation (desktop and phone sets)
  _headers                     tells Netlify to cache images for speed
