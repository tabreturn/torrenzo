# Canvas Common Cartridge Experiments (WIP)

Experiments with generating **IMS Common Cartridge (`.imscc`) packages** for import into Canvas LMS.  
Goal: author course content (HTML, images, etc.) using Torrenzo and import into Canvas programmatically.


## References

- Common Cartridge spec  
  https://www.1edtech.org/standards/cc#Started

- Canvas import documentation  
  https://community.instructure.com/en/kb/articles/660732-how-do-i-import-content-from-common-cartridge-into-canvas

- Canvas local development (Docker)  
  https://github.com/instructure/canvas-lms/wiki/Quick-Start


## Notes

Typical Canvas cartridge layout:

```
imsmanifest.xml
course_settings/module_meta.xml
wiki_content/        # Canvas pages
web_resources/       # files/images
```

`.imscc` files are just zip archives containing this structure.

