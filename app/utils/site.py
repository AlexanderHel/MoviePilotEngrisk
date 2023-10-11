from lxml import etree


class SiteUtils:

    @classmethod
    def is_logged_in(cls, html_text: str) -> bool:
        """
        Determine if the site is logged in
        :param html_text:
        :return:
        """
        html = etree.HTML(html_text)
        if not html:
            return False
        #  Presence of an obvious password entry box， Indicates not logged in
        if html.xpath("//input[@type='password']"):
            return False
        #  Presence of links to logout, user panel, etc.
        xpaths = [
            '//a[contains(@href, "logout")'
            ' or contains(@data-url, "logout")'
            ' or contains(@href, "mybonus") '
            ' or contains(@onclick, "logout")'
            ' or contains(@href, "usercp")]',
            '//form[contains(@action, "logout")]',
            '//div[@class="user-info-side"]'
        ]
        for xpath in xpaths:
            if html.xpath(xpath):
                return True
        return False

    @classmethod
    def is_checkin(cls, html_text: str) -> bool:
        """
        Determine if a site is signed in
        :return True Signed in False Not yet signed in
        """
        html = etree.HTML(html_text)
        if not html:
            return False
        #  Recognition of site check-in supportXPATH
        xpaths = [
            '//a[@id="signed"]',
            '//a[contains(@href, "attendance")]',
            '//a[contains(text(), " Sign in")]',
            '//a/b[contains(text(), " Inscribed bamboo stick (used in divination, gambling, drawing lots etc)  Until (a time)")]',
            '//span[@id="sign_in"]/a',
            '//a[contains(@href, "addbonus")]',
            '//input[@class="dt_button"][contains(@value, " Clock in or out (of a job etc)")]',
            '//a[contains(@href, "sign_in")]',
            '//a[contains(@onclick, "do_signin")]',
            '//a[@id="do-attendance"]',
            '//shark-icon-button[@href="attendance.php"]'
        ]
        for xpath in xpaths:
            if html.xpath(xpath):
                return False

        return True
