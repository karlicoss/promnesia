module.exports = {
    'plugins': [
        "flowtype",
        "react",
    ],
    'extends': [
        "eslint:recommended",
        "plugin:react/recommended",
        "plugin:flowtype/recommended",
    ],
    'settings': {
        'react': {
            'version': "detect"
        }
    },
    'env': {
        'browser': true,
        'webextensions': true,
        'node': true,
        'es6': true,
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
    // TODO use flow?
};
