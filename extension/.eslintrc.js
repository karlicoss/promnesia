module.exports = {
    "parser": "babel-eslint",
    "plugins": [
        'flowtype',
        // 'react',
    ],
    'extends': [
        // "google",
        'eslint:recommended',
        'plugin:flowtype/recommended',
        // 'plugin:react/recommended',
    ],
    'env': {
        'browser': true,
        'webextensions': true,
        'node': true,
        'es6': true,
    },

    'settings': {
        'react': {
            'version': 'detect'
        }
    },

    "parserOptions": {
        'sourceType': 'module',
        "ecmaFeatures": {
            "forOf": true,
            "modules": true,
        }
    },

    "rules": {
        "indent": "off",
        "comma-dangle": "off",
        "no-console": "off",
    }
    // https://github.com/gajus/eslint-plugin-flowtype
    // TODO use flow?
};
