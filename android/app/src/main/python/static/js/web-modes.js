/* Lightweight offline CodeMirror modes for NiceCoding's web editor.
 * The app intentionally ships local syntax modes so web editing works offline. */
(function (CodeMirror) {
  if (!CodeMirror || !CodeMirror.defineMode) return;

  CodeMirror.defineMode('javascript', function () {
    var keywords = /^(?:async|await|break|case|catch|class|const|continue|debugger|default|delete|do|else|export|extends|finally|for|from|function|if|import|in|instanceof|let|new|of|return|static|super|switch|this|throw|try|typeof|var|void|while|with|yield|true|false|null|undefined|NaN|Infinity)$/;
    return {
      startState: function () { return { blockComment: false }; },
      token: function (stream, state) {
        if (state.blockComment) {
          if (stream.skipTo('*/')) { stream.match('*/'); state.blockComment = false; }
          else stream.skipToEnd();
          return 'comment';
        }
        if (stream.eatSpace()) return null;
        if (stream.match('//')) { stream.skipToEnd(); return 'comment'; }
        if (stream.match('/*')) {
          if (!stream.skipTo('*/')) { state.blockComment = true; stream.skipToEnd(); }
          else stream.match('*/');
          return 'comment';
        }
        if (stream.match(/^(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`)/)) return 'string';
        if (stream.match(/^(?:0x[\da-f]+|\d+(?:\.\d+)?(?:e[+-]?\d+)?)/i)) return 'number';
        if (stream.match(/^[A-Za-z_$][\w$]*/)) {
          var word = stream.current();
          if (keywords.test(word)) return /^(?:true|false|null|undefined|NaN|Infinity)$/.test(word) ? 'atom' : 'keyword';
          if (/^[A-Z]/.test(word)) return 'variable-2';
          return 'variable';
        }
        if (stream.match(/^(?:===|!==|=>|==|!=|<=|>=|\+\+|--|&&|\|\||\?\?|\+=|-=|\*=|\/=|\*\*)/)) return 'operator';
        if (stream.match(/^[{}()[\],.;]/)) return 'bracket';
        if (stream.match(/^[+*/%=<>!&|?:~-]/)) return 'operator';
        stream.next(); return null;
      }
    };
  });

  CodeMirror.defineMode('css', function () {
    return {
      startState: function () { return { blockComment: false, inValue: false }; },
      token: function (stream, state) {
        if (state.blockComment) {
          if (stream.skipTo('*/')) { stream.match('*/'); state.blockComment = false; } else stream.skipToEnd();
          return 'comment';
        }
        if (stream.eatSpace()) return null;
        if (stream.match('/*')) { if (!stream.skipTo('*/')) { state.blockComment = true; stream.skipToEnd(); } else stream.match('*/'); return 'comment'; }
        if (stream.match(/^(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')/)) return 'string';
        if (stream.match(/^#[\da-f]{3,8}\b/i)) return 'number';
        if (stream.match(/^@[\w-]+/)) return 'meta';
        if (stream.match(/^[\w-]+(?=\s*:)/)) return 'property';
        if (stream.match(/^[\w-]+/)) return 'atom';
        if (stream.match(/^[{}()[\]:;,]/)) return 'bracket';
        if (stream.match(/^[.#][\w-]+/)) return 'tag';
        stream.next(); return null;
      }
    };
  });

  CodeMirror.defineMode('htmlmixed', function () {
    return {
      startState: function () { return { inTag: false, inComment: false, quote: null }; },
      token: function (stream, state) {
        if (state.inComment) {
          if (stream.skipTo('-->')) { stream.match('-->'); state.inComment = false; } else stream.skipToEnd();
          return 'comment';
        }
        if (state.quote) {
          while (!stream.eol()) {
            if (stream.next() === state.quote) { state.quote = null; break; }
          }
          return 'string';
        }
        if (stream.eatSpace()) return null;
        if (stream.match('<!--')) { if (!stream.skipTo('-->')) { state.inComment = true; stream.skipToEnd(); } else stream.match('-->'); return 'comment'; }
        if (stream.match(/^<![^>]*>/)) return 'meta';
        if (stream.match(/^<\/?[A-Za-z][\w:-]*/)) { state.inTag = true; return 'tag'; }
        if (state.inTag) {
          if (stream.match('>')) { state.inTag = false; return 'tag'; }
          if (stream.eatSpace()) return null;
          if (stream.match('/')) return null;
          if (stream.match(/^[\w:-]+(?=\s*=)/)) return 'attribute';
          if (stream.match('=')) return null;
          var ch = stream.peek();
          if (ch === '"' || ch === "'") { state.quote = stream.next(); return 'string'; }
          stream.next(); return null;
        }
        if (stream.match(/^[^<]+/)) return null;
        stream.next(); return null;
      }
    };
  });
})(window.CodeMirror);
