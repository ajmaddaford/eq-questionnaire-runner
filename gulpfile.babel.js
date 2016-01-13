import gulp from 'gulp'
import del from 'del'
import gutil from 'gulp-util'
import plumber from 'gulp-plumber'
import flatten from 'gulp-flatten'
import tap from 'gulp-tap'
import rename from 'gulp-rename'
import header from 'gulp-header'
import pkg from './package.json'
import size from 'gulp-size'
// Styles
import sass from 'gulp-sass'
import sassGlob from 'gulp-sass-glob'
import minify from 'gulp-cssnano'
import autoprefixer from 'autoprefixer'
import postcss from 'gulp-postcss'
import pxtorem from 'postcss-pxtorem'
import sourcemaps from 'gulp-sourcemaps'

// SVGs
import svgmin from 'gulp-svgmin'
import svgstore from 'gulp-svgstore'

import paths from './gulp/paths'
import bundle from './gulp/scripts'

import browserSync from './gulp/bs'

/**
 * Template for banner to add to file headers
 */

let banner = {
  full: '/*!\n' +
    ' * <%= pkg.name %> v<%= pkg.version %>: <%= pkg.description %>\n' +
    ' * (c) ' + new Date().getFullYear() + ' <%= pkg.author.name %>\n' +
    ' * <%= pkg.repository.url %>\n' +
    ' */\n\n',
  min: '/*!' +
    ' <%= pkg.name %> v<%= pkg.version %>' +
    ' | (c) ' + new Date().getFullYear() + ' <%= pkg.author.name %>' +
    ' | <%= pkg.repository.url %>' +
    ' */\n'
}

// Process, lint, and minify Sass files
gulp.task('build:styles', () => {
  gulp
    .src(paths.styles.input)
    .pipe(sourcemaps.init())
    .pipe(plumber())
    .pipe(sassGlob())
    .pipe(sass({
      errLogToConsole: true,
      outputStyle: 'expanded',
      sourceComments: false,
      onSuccess: function(msg) {
        gutil.log('Done', gutil.colors.cyan(msg))
      }
    }).on('error', function(err) {
      gutil.log(err.message.toString())
      browserSync.notify('Browserify Error!')
      this.emit('end')
    }))
    .pipe(flatten())
    .pipe(postcss([
      autoprefixer({
        browsers: ['last 1 version']
      }),
      pxtorem({
        rootValue: 16,
        propWhiteList: [],
        selectorBlackList: [],
        replace: false,
        mediaQuery: true,
        minPixelValue: 0
      })
    ]))
    .pipe(header(banner.full, {
      pkg: pkg
    }))
    .pipe(gulp.dest(paths.styles.output))
    .pipe(rename({
      suffix: '.min'
    }))
    .pipe(minify({
      discardComments: {
        removeAll: true
      }
    }))
    .pipe(header(banner.min, {
      pkg: pkg
    }))
    .pipe(sourcemaps.write('.'))
    .pipe(size({'title': 'CSS (minified)'}))
    .pipe(gulp.dest(paths.styles.output))
    .pipe(browserSync.stream({once: true}))
})

// Generate SVG sprites
gulp.task('build:svgs', ['clean:dist'], () => {
  gulp.src(paths.svgs.input)
    .pipe(plumber())
    .pipe(tap((file, t) => {
      if (file.isDirectory()) {
        let name = file.relative + '.svg'
        gulp.src(file.path + '/*.svg')
          .pipe(svgmin())
          .pipe(svgstore({
            fileName: name,
            prefix: 'icon-',
            inlineSvg: true
          }))
          .pipe(gulp.dest(paths.svgs.output))
      }
    }))
    .pipe(svgmin())
    .pipe(size({'title': 'SVG'}))
    .pipe(gulp.dest(paths.svgs.output))
})

// Copy image files into output folder
gulp.task('build:images', ['clean:dist'], () => {
  gulp.src(paths.images.input)
    .pipe(plumber())
    .pipe(gulp.dest(paths.images.output))
})

// Remove pre-existing content from output and test folders
gulp.task('clean:dist', () => {
  del.sync([
    paths.output
  ])
})

// Remove pre-existing content from text folders
gulp.task('clean:test', () => {
  del.sync([
    paths.test.coverage,
    paths.test.results
  ])
})

// Run unit tests
gulp.task('test:scripts', () => {
  gulp.src([paths.test.input].concat([paths.test.spec]))
    .pipe(plumber())
    .pipe(karma({
      configFile: paths.test.karma
    }))
    .on('error', (err) => {
      throw err
    })
})

// Spin up livereload server and listen for file changes
gulp.task('listen', () => {
  browserSync.init({
    proxy: 'eq-survey-runner.dev:5000',
    browser: false
  })
  gulp.watch(paths.styles.input, ['build:styles']).on('change', browserSync.reload)
  gulp.watch(paths.templates.input).on('change', browserSync.reload)
})

// gulp.task('copy:dist', function() {
//   gulp.src('app/*.html')
//     .pipe(plumber())
//     .pipe(gulp.dest(paths.output))
// })

/**
 * Task Runners
 */

// Compile files
gulp.task('compile', [
  'lint:scripts',
  'clean:dist',
  'build:scripts',
  'build:styles',
  'build:images',
  'build:svgs'
])

/**
 * First bundle, then serve from the ./app directory
 */
gulp.task('default', [
  'compile'
])

// Compile files and generate docs when something changes
gulp.task('watch', [
  'default',
  'listen'
])

// Run unit tests
gulp.task('test', [
  'default',
  'test:scripts'
])

gulp.task('build:scripts', ['clean:dist'], () => {
  bundle()
})
