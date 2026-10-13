"""Trimmed-down copies of real API response shapes (per each API's docs/types),
used to test that every connector normalizes correctly without network."""

OPENVERSE_IMAGES = {
    "result_count": 2, "page_count": 3, "page_size": 20, "page": 1,
    "results": [
        {"id": "4bc43a04-ef46-4544-a0c1-63c63f56e276", "title": "Neon rain street", "indexed_on": "2023-01-01T00:00:00Z",
         "foreign_landing_url": "https://www.flickr.com/photos/ana/1", "url": "https://live.staticflickr.com/1/1_o.jpg",
         "creator": "Ana", "creator_url": "https://www.flickr.com/photos/ana", "license": "by-sa", "license_version": "2.0",
         "license_url": "https://creativecommons.org/licenses/by-sa/2.0/", "provider": "flickr", "source": "flickr",
         "category": "photograph", "filesize": None, "filetype": "jpg",
         "tags": [{"name": "neon", "accuracy": None}, {"name": "rain"}], "attribution": "\"Neon rain street\" by Ana is licensed under CC BY-SA 2.0.",
         "fields_matched": ["title"], "mature": False, "height": 1200, "width": 800,
         "thumbnail": "https://api.openverse.org/v1/images/4bc43a04-ef46-4544-a0c1-63c63f56e276/thumb/",
         "detail_url": "https://api.openverse.org/v1/images/4bc43a04/", "related_url": "https://api.openverse.org/v1/images/4bc43a04/related/"},
        {"id": "mature-1", "title": "hidden", "foreign_landing_url": "https://x", "url": "https://x/1.jpg", "creator": None,
         "license": "by", "license_version": "4.0", "license_url": None, "provider": "flickr", "source": "flickr",
         "tags": None, "attribution": "", "mature": True, "height": 10, "width": 10, "thumbnail": "https://x/t"},
    ],
}

OPENVERSE_AUDIO = {
    "result_count": 1, "page_count": 1, "page_size": 20, "page": 1,
    "results": [
        {"id": "aud-1", "title": "Whoosh fast", "foreign_landing_url": "https://freesound.org/s/1/", "url": "https://cdn/1.mp3",
         "creator": "sfxguy", "license": "cc0", "license_version": "1.0", "license_url": None, "provider": "freesound",
         "source": "freesound", "category": "sound_effect", "genres": ["foley"], "tags": [{"name": "whoosh"}],
         "attribution": "x", "mature": False, "thumbnail": None, "duration": 1250, "waveform": "https://api/wave"},
    ],
}

WIKIMEDIA = {
    "batchcomplete": True,
    "continue": {"gsroffset": 30, "continue": "gsroffset||"},
    "query": {"pages": [
        {"pageid": 222, "ns": 6, "title": "File:Tokyo_neon_night.jpg", "index": 2, "imageinfo": [{
            "size": 123, "width": 4000, "height": 3000, "url": "https://upload.wikimedia.org/wikipedia/commons/a/ab/Tokyo_neon_night.jpg",
            "descriptionurl": "https://commons.wikimedia.org/wiki/File:Tokyo_neon_night.jpg",
            "thumburl": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Tokyo_neon_night.jpg/500px-Tokyo_neon_night.jpg",
            "mime": "image/jpeg",
            "extmetadata": {"LicenseShortName": {"value": "CC BY-SA 4.0"},
                            "LicenseUrl": {"value": "https://creativecommons.org/licenses/by-sa/4.0"},
                            "Artist": {"value": "<a href=\"//commons.wikimedia.org/wiki/User:Kei\">Kei</a>"},
                            "ImageDescription": {"value": "Neon signs in <b>Shinjuku</b>"},
                            "Categories": {"value": "Neon signs|Night in Tokyo"}}}]},
        {"pageid": 111, "ns": 6, "title": "File:Rain_loop.webm", "index": 1, "imageinfo": [{
            "width": 1920, "height": 1080, "url": "https://upload.wikimedia.org/wikipedia/commons/1/11/Rain_loop.webm",
            "descriptionurl": "https://commons.wikimedia.org/wiki/File:Rain_loop.webm",
            "thumburl": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/11/Rain_loop.webm/480px--Rain_loop.webm.jpg",
            "mime": "video/webm", "extmetadata": {"LicenseShortName": {"value": "CC0"}}}]},
        {"pageid": 333, "ns": 6, "title": "File:Doc.pdf", "index": 3, "imageinfo": [{"mime": "application/pdf", "url": "https://x"}]},
    ]},
}

POLYHAVEN_ASSETS = {
    "studio_small_08": {"name": "Studio Small 08", "type": 0, "date_published": 1600000000, "download_count": 50000,
                        "authors": {"Sergej Majboroda": "All"}, "categories": ["studio", "indoor"], "tags": ["softbox", "lights"],
                        "max_resolution": [16384, 8192], "thumbnail_url": "https://cdn.polyhaven.com/asset_img/thumbs/studio_small_08.png?width=256&height=256"},
    "rusty_metal": {"name": "Rusty Metal", "type": 1, "download_count": 12000, "authors": {"Rob Tuytel": "All"},
                    "categories": ["metal"], "tags": ["rust", "old"]},
    "wooden_chair": {"name": "Wooden Chair", "type": 2, "download_count": 900, "authors": {"Kenney": "All"},
                     "categories": ["furniture"], "tags": ["chair", "wood"]},
}
POLYHAVEN_FILES_HDRI = {"hdri": {"1k": {"hdr": {"url": "https://dl.polyhaven.org/file/ph-assets/HDRIs/hdr/1k/studio_small_08_1k.hdr"}},
                                 "2k": {"hdr": {"url": "https://dl.polyhaven.org/file/ph-assets/HDRIs/hdr/2k/studio_small_08_2k.hdr"}}},
                        "tonemapped": {"url": "https://x.jpg"}}
POLYHAVEN_FILES_TEXTURE = {
    "Diffuse": {"2k": {"jpg": {"url": "https://dl.polyhaven.org/t/rusty_metal_diff_2k.jpg"}}},
    "nor_gl": {"2k": {"jpg": {"url": "https://dl.polyhaven.org/t/rusty_metal_nor_gl_2k.jpg"}}},
    "blend": {"2k": {"blend": {"url": "https://dl.polyhaven.org/t/rusty_metal_2k.blend"}}},
}

AMBIENTCG = {
    "numberOfResults": 1,
    "foundAssets": [{
        "assetId": "Metal012", "releaseDate": "2019-01-01", "dataType": "Material", "downloadCount": 99999,
        "displayName": "Metal 012", "displayCategory": "Metal", "tags": ["metal", "scratched"],
        "shortLink": "https://ambientcg.com/a/Metal012",
        "previewImage": {"64-PNG": "https://acg-media.struffelproductions.com/file/ambientCG-Web/media/thumbnail/64-PNG/Metal012.png",
                         "256-PNG": "https://acg-media.struffelproductions.com/file/ambientCG-Web/media/thumbnail/256-PNG/Metal012.png",
                         "1024-PNG": "https://acg-media.struffelproductions.com/file/ambientCG-Web/media/thumbnail/1024-PNG/Metal012.png"},
        "downloadFolders": {"default": {"downloadFiletypeCategories": {"zip": {"downloads": [
            {"attribute": "1K-JPG", "fullDownloadPath": "https://ambientcg.com/get?file=Metal012_1K-JPG.zip", "size": 1000},
            {"attribute": "2K-JPG", "fullDownloadPath": "https://ambientcg.com/get?file=Metal012_2K-JPG.zip", "size": 4000},
        ]}}}},
    }],
}

NASA = {"collection": {
    "items": [
        {"href": "https://images-assets.nasa.gov/image/PIA12235/collection.json",
         "data": [{"nasa_id": "PIA12235", "title": "Crab Nebula", "media_type": "image", "center": "JPL",
                   "keywords": ["nebula", "supernova"], "date_created": "2009-10-29T00:00:00Z", "description": "A <b>supernova</b> remnant."}],
         "links": [{"href": "https://images-assets.nasa.gov/image/PIA12235/PIA12235~thumb.jpg", "rel": "preview", "render": "image"}]},
        {"href": "https://images-assets.nasa.gov/video/Launch Clip/collection.json",
         "data": [{"nasa_id": "Launch Clip", "title": "Launch", "media_type": "video", "center": "KSC", "keywords": ["rocket"]}],
         "links": [{"href": "https://images-assets.nasa.gov/video/Launch Clip/Launch Clip~thumb.jpg", "rel": "preview", "render": "image"}]},
    ],
    "metadata": {"total_hits": 2},
    "links": [{"rel": "next", "prompt": "Next", "href": "https://images-api.nasa.gov/search?page=2"}],
}}
NASA_MANIFEST = [
    "http://images-assets.nasa.gov/video/Launch Clip/Launch Clip~orig.mp4",
    "http://images-assets.nasa.gov/video/Launch Clip/Launch Clip~medium.mp4",
    "http://images-assets.nasa.gov/video/Launch Clip/Launch Clip~mobile.mp4",
]

MET_SEARCH = {"total": 3, "objectIDs": [436535, 999, 1000]}  # v1.1/search (paginated)
MET_OBJECT = {"objectID": 436535, "isPublicDomain": True, "primaryImage": "https://images.metmuseum.org/CRDImages/ep/original/DT1502.jpg",
              "primaryImageSmall": "https://images.metmuseum.org/CRDImages/ep/web-large/DT1502.jpg", "department": "European Paintings",
              "title": "Wheat Field with Cypresses", "artistDisplayName": "Vincent van Gogh", "objectDate": "1889", "medium": "Oil on canvas",
              "classification": "Paintings", "objectURL": "https://www.metmuseum.org/art/collection/search/436535",
              "tags": [{"term": "Landscapes"}, {"term": "Cypresses"}]}
MET_OBJECT_PRIVATE = {"objectID": 999, "isPublicDomain": False, "primaryImage": "", "primaryImageSmall": "", "title": "Modern"}

ARTIC = {
    "pagination": {"total": 40, "limit": 2, "total_pages": 20, "current_page": 1},
    "data": [{"id": 27992, "title": "A Sunday on La Grande Jatte", "image_id": "1adf2696-8489-499b-cad2-821d7fde4b33",
              "artist_title": "Georges Seurat", "artist_display": "Georges Seurat\nFrench, 1859-1891", "is_public_domain": True,
              "thumbnail": {"lqip": "data:image/gif;base64,xx", "width": 3000, "height": 2016, "alt_text": "painting"},
              "term_titles": ["pointillism"], "style_titles": ["Post-Impressionism"], "subject_titles": ["leisure"],
              "classification_titles": ["painting"], "date_display": "1884", "color": {"h": 200, "l": 50, "s": 60, "percentage": 0.2},
              "medium_display": "Oil on canvas"},
             {"id": 1, "title": "No image", "image_id": None, "is_public_domain": True}],
    "config": {"iiif_url": "https://www.artic.edu/iiif/2", "website_url": "http://www.artic.edu"},
}

CLEVELAND = {"info": {"total": 1}, "data": [{
    "id": 94979, "accession_number": "1958.31", "title": "Twilight in the Wilderness", "creation_date": "1860",
    "creators": [{"description": "Frederic Edwin Church (American, 1826-1900)", "role": "artist"}], "type": "Painting",
    "technique": "oil on canvas", "department": "American Painting and Sculpture", "culture": ["America, 19th century"],
    "url": "https://clevelandart.org/art/1965.233", "share_license_status": "CC0", "description": "Sunset over the wilderness.",
    "images": {"web": {"url": "https://openaccess-cdn.clevelandart.org/1965.233/1965.233_web.jpg", "width": 893, "height": 600},
               "print": {"url": "https://openaccess-cdn.clevelandart.org/1965.233/1965.233_print.jpg", "width": 3400, "height": 2284}}}]}

SMITHSONIAN = {"status": 200, "responseCode": 1, "response": {"rowCount": 1, "rows": [{
    "id": "edanmdm-nmah_1", "title": "Poster", "unitCode": "NMAH",
    "content": {
        "descriptiveNonRepeating": {
            "record_ID": "nmah_1", "title": {"label": "Title", "content": "Neon sign poster"}, "data_source": "National Museum of American History",
            "record_link": "http://n2t.net/ark:/65665/ng49ca746",
            "online_media": {"mediaCount": 1, "media": [{"thumbnail": "https://ids.si.edu/ids/deliveryService?id=NMAH-1&max=150",
                                                          "content": "https://ids.si.edu/ids/deliveryService?id=NMAH-1", "type": "Images",
                                                          "usage": {"access": "CC0"}}]}},
        "indexedStructured": {"object_type": ["Posters"], "topic": ["Advertising", "Lighting"]}}}]}}

EUROPEANA = {"totalResults": 1, "itemsCount": 1, "items": [{
    "id": "/2021672/resource_document_mauritshuis_670", "title": ["Girl with a Pearl Earring"], "type": "IMAGE",
    "dcCreator": ["Johannes Vermeer"], "dataProvider": ["Mauritshuis"],
    "edmPreview": ["https://api.europeana.eu/thumbnail/v2/url.json?uri=https%3A%2F%2Fx&type=IMAGE"],
    "edmIsShownBy": ["https://www.mauritshuis.nl/media/670.jpg"], "rights": ["http://creativecommons.org/publicdomain/mark/1.0/"],
    "guid": "https://www.europeana.eu/item/2021672/resource_document_mauritshuis_670?utm_source=api&utm_medium=api",
    "edmConceptLabel": [{"def": "painting"}], "year": ["1665"]}]}

ARCHIVE = {"response": {"numFound": 2, "start": 0, "docs": [
    {"identifier": "Neon_Signs_1955", "title": "Neon Signs (1955)", "mediatype": "movies",
     "licenseurl": "http://creativecommons.org/publicdomain/mark/1.0/", "creator": "Prelinger Archives",
     "subject": ["neon; signs", "advertising"], "downloads": 5000, "description": "<p>Ephemeral film</p>", "date": "1955-01-01T00:00:00Z"},
    {"identifier": "mystery_tape", "title": "Mystery tape", "mediatype": "audio", "downloads": 3},
]}}
ARCHIVE_METADATA = {"files": [
    {"name": "Neon_Signs_1955.thumbs/x.jpg", "format": "Thumbnail"},
    {"name": "Neon_Signs_1955_512kb.mp4", "format": "512Kb MPEG4"},
    {"name": "Neon_Signs_1955.mp4", "format": "h.264"},
]}

ICONIFY = {"icons": ["mdi:weather-rainy", "ph:cloud-rain-bold"], "total": 2, "limit": 64, "start": 0,
           "collections": {"mdi": {"name": "Material Design Icons", "total": 7000, "author": {"name": "Pictogrammers", "url": "https://github.com/Templarian/MaterialDesign"},
                                   "license": {"title": "Apache 2.0", "spdx": "Apache-2.0", "url": "https://github.com/Templarian/MaterialDesign/blob/master/LICENSE"},
                                   "category": "Material"},
                           "ph": {"name": "Phosphor", "author": {"name": "Phosphor Icons"}, "license": {"title": "MIT", "spdx": "MIT"}}}}

FONTSOURCE = [
    {"id": "space-mono", "family": "Space Mono", "subsets": ["latin", "latin-ext"], "weights": [400, 700], "styles": ["italic", "normal"],
     "defSubset": "latin", "variable": False, "lastModified": "2022-09-22", "category": "monospace", "version": "v12", "type": "google"},
    {"id": "abril-fatface", "family": "Abril Fatface", "subsets": ["latin"], "weights": [400], "styles": ["normal"],
     "defSubset": "latin", "variable": False, "lastModified": "2022-09-22", "category": "display", "version": "v19", "type": "google"},
    {"id": "inter", "family": "Inter", "subsets": ["latin"], "weights": [100, 400, 900], "styles": ["normal"],
     "defSubset": "latin", "variable": True, "category": "sans-serif", "type": "google"},
]

GITHUB = {"total_count": 2, "incomplete_results": False, "items": [
    {"id": 1, "full_name": "airbnb/lottie-web", "name": "lottie-web", "html_url": "https://github.com/airbnb/lottie-web",
     "description": "Render After Effects animations natively on Web", "owner": {"login": "airbnb", "html_url": "https://github.com/airbnb"},
     "stargazers_count": 30000, "topics": ["animation", "after-effects"], "language": "JavaScript",
     "license": {"key": "mit", "spdx_id": "MIT", "url": "https://api.github.com/licenses/mit"}, "default_branch": "master", "pushed_at": "2024-05-01T00:00:00Z"},
    {"id": 2, "full_name": "someone/cool-shaders", "html_url": "https://github.com/someone/cool-shaders", "description": "shaders",
     "owner": {"login": "someone"}, "stargazers_count": 12, "topics": [], "license": None, "default_branch": "main"},
]}

ARENA_SEARCH = {"term": "brutalism", "total_pages": 500, "current_page": 1, "per": 6, "length": 6, "authenticated": False,
                "users": [], "blocks": [], "channels": [
    {"id": 1329135, "slug": "nu-brutalism", "title": "Nu-Brutalism", "length": 50, "status": "closed", "nsfw?": False},
    {"id": 9, "slug": "empty-one", "title": "Empty", "length": 0},
]}
ARENA_CHANNEL = {"contents": [
    {"id": 1001, "title": "Concrete poster", "generated_title": "poster.jpg", "class": "Image", "base_class": "Block",
     "description": "Swiss grid", "created_at": "2021-03-01T00:00:00Z", "connection_count": 12,
     "image": {"content_type": "image/jpeg", "thumb": {"url": "https://d2w9rnfcy7mm78.cloudfront.net/1/thumb.jpg"},
               "display": {"url": "https://d2w9rnfcy7mm78.cloudfront.net/1/display.jpg"},
               "large": {"url": "https://d2w9rnfcy7mm78.cloudfront.net/1/large.jpg"},
               "original": {"url": "https://d2w9rnfcy7mm78.cloudfront.net/1/original.jpg"}},
     "source": {"url": "https://example.com/poster", "provider": {"name": "Example", "url": "https://example.com"}},
     "user": {"slug": "ana-k", "username": "ana", "full_name": "Ana K"}},
    {"id": 1002, "title": "Just text", "class": "Text", "content": "hello"},
    {"id": 1003, "title": "", "generated_title": "loop.gif", "class": "Image",
     "image": {"content_type": "image/gif", "display": {"url": "https://d2w/3/display.gif"}, "original": {"url": "https://d2w/3/o.gif"}},
     "user": {"slug": "bo", "username": "bo"}},
]}
ARENA_CHANNELS = {"length": 2, "channels": [
    {"id": 1, "slug": "big-catch-all", "title": "Everything", "length": 5000},
    {"id": 2, "slug": "concrete-dreams", "title": "Concrete dreams", "length": 40},
]}
ARENA_CONTENTS = {"length": 2, "contents": [
    {"id": 2001, "title": "Raw facade", "class": "Image", "image": {"content_type": "image/jpeg", "display": {"url": "https://d2w/2001.jpg"}},
     "user": {"slug": "c", "username": "c"}},
    {"id": 1001, "title": "Concrete poster", "class": "Image", "image": {"content_type": "image/jpeg", "display": {"url": "https://d2w/1001.jpg"}},
     "user": {"slug": "c", "username": "c"}},
]}

LOTTIE = {"data": {"searchPublicAnimations": {
    "edges": [{"cursor": "c1", "node": {
        "id": 12345, "name": "Loading dots", "url": "https://lottiefiles.com/free-animation/loading-dots-abc",
        "lottieUrl": "https://assets-v2.lottiefiles.com/a/1.lottie", "jsonUrl": "https://assets-v2.lottiefiles.com/a/1.json",
        "gifUrl": "https://assets-v2.lottiefiles.com/a/1.gif", "imageUrl": "https://assets-v2.lottiefiles.com/a/1.png",
        "videoUrl": "https://assets-v2.lottiefiles.com/a/1.mp4", "bgColor": "#FFFFFF", "downloads": 1000, "likesCount": 20,
        "createdBy": {"username": "anim8", "firstName": "An", "lastName": "Im"}}}],
    "pageInfo": {"hasNextPage": True, "endCursor": "c1"}}}}
LOTTIE_ERROR = {"errors": [{"message": "Cannot query field \"likesCount\" on type \"PublicAnimation\"."}], "data": None}

CIVITAI = {"items": [
    {"id": 101, "url": "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/abc/original=true/101.jpeg", "hash": "U", "width": 832,
     "height": 1216, "nsfwLevel": "None", "type": "image", "nsfw": False, "browsingLevel": 1, "createdAt": "2025-01-01T00:00:00.000Z",
     "postId": 1, "stats": {"likeCount": 10, "heartCount": 5}, "username": "maker",
     "meta": {"prompt": "cinematic neon city at night, rain, reflections", "negativePrompt": "blurry", "Model": "flux"},
     "baseModel": "Flux.1 D", "tags": [{"id": 1, "name": "city"}]},
    {"id": 102, "url": "https://image.civitai.com/x/def/original=true/102.jpeg", "width": 512, "height": 512, "nsfwLevel": "X",
     "type": "image", "nsfw": True, "browsingLevel": 8, "stats": {}, "username": "x", "meta": {"prompt": "neon"}},
    {"id": 103, "url": "https://image.civitai.com/x/ghi/original=true/103.jpeg", "width": 512, "height": 512, "nsfwLevel": "None",
     "type": "image", "nsfw": False, "browsingLevel": 1, "stats": {"likeCount": 99}, "username": "y",
     "meta": {"prompt": "a cute cat portrait"}},
], "metadata": {"nextCursor": None}}

PEXELS_PHOTOS = {"page": 1, "per_page": 30, "total_results": 1, "next_page": "https://api.pexels.com/v1/search/?page=2", "photos": [
    {"id": 2014422, "width": 3024, "height": 3024, "url": "https://www.pexels.com/photo/neon-lights-2014422/",
     "photographer": "Joey Farina", "photographer_url": "https://www.pexels.com/@joey", "photographer_id": 680589,
     "avg_color": "#978E82", "alt": "Neon lights in the rain",
     "src": {"original": "https://images.pexels.com/photos/2014422/pexels-photo-2014422.jpeg",
             "large2x": "https://images.pexels.com/photos/2014422/pexels-photo-2014422.jpeg?h=650&dpr=2",
             "large": "https://images.pexels.com/photos/2014422/pexels-photo-2014422.jpeg?h=650",
             "medium": "https://images.pexels.com/photos/2014422/pexels-photo-2014422.jpeg?h=350",
             "small": "https://images.pexels.com/photos/2014422/pexels-photo-2014422.jpeg?h=130"}}]}
PEXELS_VIDEOS = {"page": 1, "per_page": 30, "total_results": 1, "videos": [
    {"id": 1448735, "width": 3840, "height": 2160, "duration": 12, "url": "https://www.pexels.com/video/rain-on-window-at-night-1448735/",
     "image": "https://images.pexels.com/videos/1448735/free-video-1448735.jpg", "user": {"id": 1, "name": "Mikhail", "url": "https://www.pexels.com/@mikhail"},
     "video_files": [
         {"id": 1, "quality": "sd", "file_type": "video/mp4", "width": 640, "height": 360, "fps": 25, "link": "https://player.vimeo.com/sd.mp4"},
         {"id": 2, "quality": "hd", "file_type": "video/mp4", "width": 1920, "height": 1080, "fps": 25, "link": "https://player.vimeo.com/hd.mp4"},
         {"id": 3, "quality": "uhd", "file_type": "video/mp4", "width": 3840, "height": 2160, "fps": 25, "link": "https://player.vimeo.com/uhd.mp4"},
         {"id": 4, "quality": "hls", "file_type": "application/x-mpegURL", "width": None, "height": None, "link": "https://x.m3u8"}],
     "video_pictures": []}]}

PIXABAY_IMAGES = {"total": 1, "totalHits": 1, "hits": [
    {"id": 195893, "pageURL": "https://pixabay.com/photos/neon-light-195893/", "type": "photo", "tags": "neon, light, sign",
     "previewURL": "https://cdn.pixabay.com/photo/2013/10/15/09/12/neon-195893_150.jpg",
     "webformatURL": "https://pixabay.com/get/35bbf209e13e39d2_640.jpg", "largeImageURL": "https://pixabay.com/get/ed6a99fd0a76647_1280.jpg",
     "imageWidth": 4000, "imageHeight": 2250, "views": 7671, "downloads": 6439, "likes": 5, "user_id": 48777, "user": "Josch13"}]}
PIXABAY_VIDEOS = {"total": 1, "totalHits": 1, "hits": [
    {"id": 125, "pageURL": "https://pixabay.com/videos/id-125/", "type": "animation", "tags": "abstract, loop, neon", "duration": 12,
     "videos": {"large": {"url": "https://cdn.pixabay.com/video/125_large.mp4", "width": 1920, "height": 1080, "size": 6615235, "thumbnail": "https://cdn.pixabay.com/video/125_large.jpg"},
                "medium": {"url": "https://cdn.pixabay.com/video/125_medium.mp4", "width": 1280, "height": 720, "size": 3562083, "thumbnail": "https://cdn.pixabay.com/video/125_medium.jpg"},
                "small": {"url": "https://cdn.pixabay.com/video/125_small.mp4", "width": 640, "height": 360, "size": 1030736, "thumbnail": ""},
                "tiny": {"url": "https://cdn.pixabay.com/video/125_tiny.mp4", "width": 480, "height": 270, "size": 426799, "thumbnail": ""}},
     "views": 4462, "downloads": 1464, "likes": 18, "user_id": 1, "user": "Coverr-Free-Footage"}]}

UNSPLASH = {"total": 133, "total_pages": 7, "results": [
    {"id": "eOLpJytrbsQ", "width": 4000, "height": 6000, "color": "#A7A2A1", "blur_hash": "LaLXMa9Fx[D%~q%MtQM|kDRjtRIU",
     "likes": 12, "description": "A man drinking a coffee.", "alt_description": "man in black coat",
     "urls": {"raw": "https://images.unsplash.com/photo-1?ixid=x", "full": "https://images.unsplash.com/photo-1?q=85",
              "regular": "https://images.unsplash.com/photo-1?w=1080", "small": "https://images.unsplash.com/photo-1?w=400",
              "thumb": "https://images.unsplash.com/photo-1?w=200"},
     "links": {"self": "https://api.unsplash.com/photos/eOLpJytrbsQ", "html": "https://unsplash.com/photos/eOLpJytrbsQ",
               "download": "https://unsplash.com/photos/eOLpJytrbsQ/download",
               "download_location": "https://api.unsplash.com/photos/eOLpJytrbsQ/download?ixid=x"},
     "user": {"username": "jimmyexample", "name": "James", "links": {"html": "https://unsplash.com/@jimmyexample"}},
     "tags": [{"type": "search", "title": "coffee"}]}]}

FREESOUND = {"count": 1, "next": None, "previous": None, "results": [
    {"id": 60013, "name": "Whoosh 01.wav", "tags": ["whoosh", "swoosh", "transition"], "description": "A fast whoosh",
     "license": "http://creativecommons.org/publicdomain/zero/1.0/", "username": "qubodup", "duration": 0.9,
     "url": "https://freesound.org/people/qubodup/sounds/60013/", "num_downloads": 9999,
     "previews": {"preview-hq-mp3": "https://cdn.freesound.org/previews/60/60013_hq.mp3", "preview-lq-mp3": "https://cdn.freesound.org/previews/60/60013_lq.mp3"},
     "images": {"waveform_m": "https://cdn.freesound.org/displays/60/60013_wave_M.png"}}]}

GIPHY = {"data": [
    {"type": "gif", "id": "l0HlBO7eyXzSZkJri", "url": "https://giphy.com/gifs/neon-l0HlBO7eyXzSZkJri", "title": "Neon Glow GIF",
     "username": "neonartist", "rating": "g", "user": {"display_name": "Neon Artist", "profile_url": "https://giphy.com/neonartist"},
     "images": {"fixed_width_still": {"url": "https://media.giphy.com/media/l0HlBO7eyXzSZkJri/200w_s.gif", "width": "200", "height": "113"},
                "fixed_width": {"url": "https://media.giphy.com/media/l0HlBO7eyXzSZkJri/200w.gif", "width": "200", "height": "113",
                                "mp4": "https://media.giphy.com/media/l0HlBO7eyXzSZkJri/200w.mp4", "webp": "https://media.giphy.com/200w.webp"},
                "original": {"url": "https://media.giphy.com/media/l0HlBO7eyXzSZkJri/giphy.gif", "width": "480", "height": "270",
                             "mp4": "https://media.giphy.com/media/l0HlBO7eyXzSZkJri/giphy.mp4"}}}],
    "pagination": {"total_count": 500, "count": 1, "offset": 0}, "meta": {"status": 200}}

REDDIT_TOKEN = {"access_token": "tok", "token_type": "bearer", "expires_in": 86400, "scope": "*"}
REDDIT_SEARCH = {"kind": "Listing", "data": {"after": "t3_next", "children": [
    {"kind": "t3", "data": {"id": "abc123", "title": "Liquid chrome loop I made in C4D", "subreddit": "Cinema4D", "author": "motionkid",
                            "permalink": "/r/Cinema4D/comments/abc123/liquid_chrome/", "url": "https://v.redd.it/xyz", "score": 900,
                            "over_18": False, "is_video": True, "post_hint": "hosted:video",
                            "media": {"reddit_video": {"fallback_url": "https://v.redd.it/xyz/DASH_720.mp4", "duration": 8, "width": 1280, "height": 720}},
                            "preview": {"images": [{"source": {"url": "https://preview.redd.it/big.jpg?auto=webp&s=1", "width": 1280, "height": 720},
                                                    "resolutions": [{"url": "https://preview.redd.it/320.jpg", "width": 320, "height": 180}]}]}}},
    {"kind": "t3", "data": {"id": "nsfw1", "title": "nsfw", "over_18": True, "permalink": "/r/x/", "subreddit": "x"}},
    {"kind": "t3", "data": {"id": "img1", "title": "Brutalist poster series", "subreddit": "graphic_design", "author": "des",
                            "permalink": "/r/graphic_design/comments/img1/", "url": "https://i.redd.it/poster.png", "score": 50,
                            "over_18": False, "is_video": False, "post_hint": "image",
                            "preview": {"images": [{"source": {"url": "https://preview.redd.it/poster.png?s=2", "width": 1000, "height": 1400},
                                                    "resolutions": [{"url": "https://preview.redd.it/poster-320.png", "width": 320, "height": 448}]}]}}},
]}}
