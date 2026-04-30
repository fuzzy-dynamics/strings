# Link Type Classification

## How ft-resolve classifies URLs

When `ft-resolve` follows a t.co redirect, it classifies the destination URL by examining the hostname and path. This classification determines which bookmarks contain readable content (articles, papers, repos) vs. media (images, videos).

## Classification Rules

| Type | Rule | Examples |
|------|------|---------|
| `image` | Host is `pbs.twimg.com` or path contains `/photo` | Tweet images, profile images |
| `video` | Host is `video.twimg.com`, YouTube, Vimeo, or path contains `/video` | Tweet videos, YouTube links |
| `tweet` | Host is `twitter.com` or `x.com` (not image/video/article) | Quote tweets, reply links |
| `arxiv` | Host contains `arxiv.org` | Papers, preprints |
| `repo` | Host is `github.com` or `gitlab.com` | Code repositories |
| `space` | Path contains `/i/spaces` | Twitter Spaces |
| `article` | Everything else | Blog posts, essays, news articles |

## Priority Order

Classification checks are applied in this order:
1. Image hosts (`pbs.twimg.com`)
2. Video hosts (`video.twimg.com`)
3. Twitter/X internal paths (`/photo`, `/video`, `/i/article`, `/i/spaces`)
4. Academic hosts (`arxiv.org`)
5. Code hosts (`github.com`, `gitlab.com`)
6. Video platforms (`youtube.com`, `vimeo.com`)
7. Default: `article`

## Usage in ft-articles

`ft-articles` filters bookmarks by link type:

- Default: shows `article`, `arxiv`, and `repo` types
- `--arxiv`: shows only `arxiv` types
- `--repos`: shows only `repo` types

Image, video, tweet, and space types are excluded from article listings since they don't contain fetchable text content.

## Extending Classification

To add new type classifications, edit the `classify_url()` function in `scripts/ft-resolve`. Add new hostname or path checks before the default `article` return.

Common additions:
- Substack domains -> `newsletter`
- Medium domains -> `article`
- Podcast hosts -> `podcast`
- Slide decks (speakerdeck, slideshare) -> `slides`
